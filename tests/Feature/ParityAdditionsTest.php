<?php

namespace Tests\Feature;

use App\Models\Analysis;
use App\Models\Project;
use Illuminate\Http\UploadedFile;
use Tests\TestCase;
use ZipArchive;

class ParityAdditionsTest extends TestCase
{
    private function doneAnalysis(): array
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->finishAnalysis($analysis['id'])->assertJsonPath('status', 'done');

        return [$project, $recording, $analysis];
    }

    public function test_survey_round_trip_with_photos(): void
    {
        [, , $analysis] = $this->doneAnalysis();
        $id = $analysis['id'];

        $this->getJson("/api/analyses/{$id}/survey")->assertOk()->assertJsonPath('datum', 'WGS84')->assertJsonPath('photos', []);

        $res = $this->put("/api/analyses/{$id}/survey", [
            'date' => '2024-01-05', 'client' => 'ACME Geo', 'place_id' => 'Perugia', 'address' => 'Via Roma 1',
            'latitude' => '43.11', 'longitude' => '12.39', 'elevation_m' => '490', 'weather' => 'clear', 'notes' => 'quiet site',
            'photo1' => UploadedFile::fake()->image('site.jpg', 400, 300), 'caption1' => 'Sensor',
            'photo2' => UploadedFile::fake()->image('north.png', 400, 300),
        ], ['Accept' => 'application/json'])->assertOk()->json();

        $this->assertSame('ACME Geo', $res['client']);
        $this->assertSame(43.11, $res['latitude']);
        $this->assertCount(2, $res['photos']);
        $this->assertSame('survey/photo1.jpg', $res['photos'][0]['file']);
        $this->assertSame('Sensor', $res['photos'][0]['caption']);
        $this->assertSame('survey/photo2.png', $res['photos'][1]['file']);
        $this->assertFileExists($analysis['result_dir'].'/survey/photo1.jpg');

        $this->get("/api/analyses/{$id}/survey/photo/1")->assertOk();
        $this->get("/api/analyses/{$id}/survey/photo/2")->assertOk();

        // Report context carries the survey with absolute photo paths.
        $this->postJson("/api/analyses/{$id}/report")->assertStatus(202);
        $call = collect($this->engine->calls)->firstWhere('method', 'exportReport');
        $survey = $call['payload']['context']['survey'];
        $this->assertSame('Perugia', $survey['place_id']);
        $this->assertStringStartsWith('/', $survey['photos'][0]['path']);
        $this->assertFileExists($survey['photos'][0]['path']);

        // Remove one photo, keep the other; serializer exposes the survey.
        $res = $this->put("/api/analyses/{$id}/survey", ['remove_photo1' => 1, 'weather' => 'rain'], ['Accept' => 'application/json'])->assertOk()->json();
        $this->assertCount(1, $res['photos']);
        $this->assertSame('survey/photo2.png', $res['photos'][0]['file']);
        $this->assertSame('rain', $res['weather']);
        $this->assertSame('ACME Geo', $res['client']);
        $this->assertFileDoesNotExist($analysis['result_dir'].'/survey/photo1.jpg');
        $this->getJson("/api/analyses/{$id}?include=none")->assertOk()->assertJsonPath('survey.client', 'ACME Geo');

        $this->put("/api/analyses/{$id}/survey", ['latitude' => 120], ['Accept' => 'application/json'])->assertStatus(422);
    }

    public function test_models_are_stored_and_model_hvsr_proxy_validates(): void
    {
        [, , $analysis] = $this->doneAnalysis();
        $id = $analysis['id'];
        $layers = [
            ['thickness_m' => 50, 'vs' => 155, 'vp' => 320, 'poisson' => null, 'density' => 1800, 'qs' => 30, 'qp' => 60],
            ['thickness_m' => null, 'vs' => 450, 'vp' => 800, 'density' => 2200],
        ];

        $res = $this->putJson("/api/analyses/{$id}/models", ['models' => [['name' => 'Model A', 'layers' => $layers, 'vs30_offset_m' => 5]]])->assertOk()->json();
        $this->assertCount(1, $res['models']);
        $this->assertSame('Model A', $res['models'][0]['name']);
        $this->assertNotEmpty($res['models'][0]['id']);
        $this->assertEquals(5.0, $res['models'][0]['vs30_offset_m']);
        $this->assertSame('Model A', Analysis::query()->where('ulid', $id)->first()->models[0]['name']);
        $this->getJson("/api/analyses/{$id}?include=none")->assertOk()->assertJsonPath('models.0.name', 'Model A');

        $this->putJson("/api/analyses/{$id}/models", ['models' => []])->assertOk()->assertJsonPath('models', []);
        $this->putJson("/api/analyses/{$id}/models", ['models' => [['name' => 'bad', 'layers' => [['thickness_m' => 5, 'vs' => 0]]]]])->assertStatus(422);

        $ok = $this->postJson('/api/engine/model-hvsr', ['layers' => $layers, 'freq_min' => 0.2, 'freq_max' => 20, 'n_freq' => 10])->assertOk()->json();
        $this->assertCount(10, $ok['frequency']);
        $this->assertCount(10, $ok['hvsr']);
        $this->assertEquals(0.0, $ok['layers'][0]['depth_top_m']);
        $call = collect($this->engine->calls)->firstWhere('method', 'modelHvsr');
        $this->assertSame(10, $call['payload']['n_freq']);

        // last layer must be the half-space
        $this->postJson('/api/engine/model-hvsr', ['layers' => [['thickness_m' => 10, 'vs' => 200, 'vp' => 400]]])->assertStatus(422);
        // only the last layer may lack a thickness
        $this->postJson('/api/engine/model-hvsr', ['layers' => [['thickness_m' => null, 'vs' => 200, 'vp' => 400], ['thickness_m' => null, 'vs' => 400, 'vp' => 800]]])->assertStatus(422);
        // poisson out of range
        $this->postJson('/api/engine/model-hvsr', ['layers' => [['thickness_m' => 10, 'vs' => 200, 'poisson' => 0.6], ['thickness_m' => null, 'vs' => 400, 'vp' => 800]]])->assertStatus(422);
        // vp or poisson required
        $this->postJson('/api/engine/model-hvsr', ['layers' => [['thickness_m' => 10, 'vs' => 200], ['thickness_m' => null, 'vs' => 400, 'vp' => 800]]])->assertStatus(422);
    }

    public function test_curve_upload_is_parsed_and_staging_cleaned(): void
    {
        $project = $this->createProject();
        $file = UploadedFile::fake()->createWithContent('site.hv', "# GEOPSY output\n# frequency average min max\n0.5 1.1 0.9 1.3\n1.0 2.4 2.0 2.9\n");
        $res = $this->post("/api/projects/{$project['id']}/curves", ['file' => $file], ['Accept' => 'application/json'])->assertOk()->json();
        $this->assertEquals([0.5, 1.0], $res['frequency']);
        $this->assertSame([1.1, 2.4], $res['values']);
        $this->assertSame('geopsy_hv', $res['format']);
        $this->assertSame('site.hv', $res['name']);
        $this->assertSame([], glob($this->dataDir.'/projects/'.$project['slug'].'/uploads/curve-*'));

        $this->post("/api/projects/{$project['id']}/curves", ['file' => UploadedFile::fake()->create('bad.exe', 10)], ['Accept' => 'application/json'])->assertStatus(422);
    }

    public function test_geopsy_hv_and_window_set_exports(): void
    {
        [, $recording, $analysis] = $this->doneAnalysis();
        $id = $analysis['id'];

        $hv = $this->get("/api/analyses/{$id}/exports/geopsy-hv")->assertOk();
        $this->assertStringContainsString('frequency average min max', $hv->streamedContent());

        $set = $this->getJson("/api/analyses/{$id}/exports/windows-json")->assertOk()->json();
        $this->assertSame('fixed', $set['mode']);
        $this->assertSame($recording['id'], $set['recording']);
        $this->assertCount(3, $set['windows']);
        $this->assertSame(30, $set['windows'][1]['start_s']);
        $this->assertFalse($set['windows'][1]['accepted']);
        $this->assertSame('sta_lta', $set['windows'][1]['reason']);

        // and the set can be imported back as custom windows with overrides
        $imp = $this->postJson("/api/recordings/{$recording['id']}/windows/import", $set)->assertOk()->json();
        $this->assertSame('custom', $imp['mode']);
        $this->assertEquals([[0, 60], [30, 90], [60, 120]], $imp['custom']);
        $this->assertSame(['accepted' => false, 'reason' => 'manual'], $imp['window_overrides']['1']);
        $this->assertSame(3, $imp['counts']['imported']);
    }

    public function test_windows_import_normalises_and_rejects_bad_windows(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);   // fake duration 600 s
        $res = $this->postJson("/api/recordings/{$recording['id']}/windows/import", ['windows' => [
            ['start_s' => 10, 'end_s' => 70, 'accepted' => true],
            ['start_s' => 100, 'end_s' => 50],                 // inverted → skipped
            ['start_s' => 590, 'end_s' => 700],                // clipped to duration
            ['start_s' => 900, 'end_s' => 960],                // beyond record → skipped
        ]])->assertOk()->json();
        $this->assertEquals([[10, 70], [590, 600]], $res['custom']);
        $this->assertSame(2, $res['counts']['skipped']);
        $this->postJson("/api/recordings/{$recording['id']}/windows/import", ['windows' => [['start_s' => 700, 'end_s' => 800]]])->assertStatus(422);
        $this->postJson("/api/recordings/{$recording['id']}/windows/import", ['windows' => []])->assertStatus(422);
    }

    public function test_full_resolution_samples_for_the_player(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $res = $this->getJson("/api/recordings/{$recording['id']}/samples?component=z&t_start=0&t_end=2")->assertOk()->json();
        $this->assertEquals(100.0, $res['fs']);
        $this->assertEquals(0.0, $res['t0']);
        $this->assertSame([1, 2, 3, 4, 5], $res['values']);
        $call = collect($this->engine->calls)->last(fn ($c) => $c['method'] === 'recordingData');
        $this->assertSame(['z'], $call['payload']['components']);
        $this->assertGreaterThanOrEqual(60000, $call['payload']['max_points']);

        $this->getJson("/api/recordings/{$recording['id']}/samples?component=x")->assertStatus(422);
        $this->getJson("/api/recordings/{$recording['id']}/samples?component=z&t_start=0&t_end=90000")->assertStatus(422);
    }

    public function test_backup_and_restore_round_trip(): void
    {
        [$project, $recording, $analysis] = $this->doneAnalysis();
        $this->postJson("/api/projects/{$project['id']}/stations", ['code' => 'ST1', 'name' => 'Station one', 'elevation' => 12])->assertCreated();
        $this->putJson("/api/analyses/{$analysis['id']}/models", ['models' => [['name' => 'M', 'layers' => [['thickness_m' => null, 'vs' => 300, 'vp' => 600]]]]])->assertOk();

        $response = $this->get("/api/projects/{$project['id']}/backup")->assertOk();
        $this->assertStringContainsString('backup.zip', (string) $response->headers->get('content-disposition'));
        $zipPath = $this->dataDir.'/round-trip.zip';
        file_put_contents($zipPath, $response->getFile()->getContent());

        $zip = new ZipArchive;
        $this->assertTrue($zip->open($zipPath));
        $dump = json_decode($zip->getFromName('database.json'), true);
        $this->assertSame('quakelogic-hvsr-studio-backup/1', $dump['format']);
        $this->assertCount(1, $dump['recordings']);
        $this->assertCount(1, $dump['analyses']);
        $this->assertCount(1, $dump['stations']);
        $this->assertNotFalse($zip->locateName('project/analyses/'.$analysis['id'].'/result.json'));
        $this->assertNotFalse($zip->locateName('project/traces/'.$recording['id'].'.npz'));
        $zip->close();

        // Restore into the same installation: slug gets a suffix, ULIDs collide → new ones, paths rewritten.
        $restored = $this->post('/api/projects/restore', ['file' => new UploadedFile($zipPath, 'round-trip.zip', 'application/zip', null, true)], ['Accept' => 'application/json'])
            ->assertCreated()->json();
        $this->assertNotSame($project['id'], $restored['id']);
        $this->assertSame($project['name'], $restored['name']);
        $this->assertNotSame($project['slug'], $restored['slug']);
        $this->assertCount(1, $restored['recordings']);
        $this->assertCount(1, $restored['stations']);
        $rec = $restored['recordings'][0];
        $this->assertNotSame($recording['id'], $rec['id']);
        $this->assertSame('ready', $rec['status']);
        $this->assertCount(1, $rec['analyses']);

        $newProject = Project::query()->where('ulid', $restored['id'])->firstOrFail();
        $newRec = $newProject->recordings()->firstOrFail();
        $this->assertStringStartsWith($this->dataDir.'/projects/'.$restored['slug'].'/', $newRec->canonical_path);
        $this->assertFileExists($newRec->canonical_path);
        $newAnalysis = $newProject->analyses()->firstOrFail();
        $this->assertStringStartsWith($this->dataDir.'/projects/'.$restored['slug'].'/analyses/', $newAnalysis->result_dir);
        $this->assertFileExists($newAnalysis->result_dir.'/result.json');
        $this->assertSame('M', $newAnalysis->models[0]['name']);
        $this->assertSame($newRec->id, $newAnalysis->recording_id);
        $this->assertSame($newProject->stations()->first()->id, $newRec->station_id ?? $newProject->stations()->first()->id);
        $this->assertDatabaseHas('activity_log', ['action' => 'project.restored', 'project_id' => $newProject->id]);
        $this->assertDatabaseHas('activity_log', ['action' => 'project.backup', 'project_id' => Project::query()->where('ulid', $project['id'])->value('id')]);

        // The restored analysis is fully usable through the API.
        $this->getJson("/api/analyses/{$newAnalysis->ulid}")->assertOk()->assertJsonPath('status', 'done');

        // Garbage input is rejected cleanly.
        $this->post('/api/projects/restore', ['file' => UploadedFile::fake()->createWithContent('x.zip', 'not a zip')], ['Accept' => 'application/json'])->assertStatus(422);
    }

    public function test_saf_and_seismic_formats_are_accepted(): void
    {
        $project = $this->createProject();
        $files = [UploadedFile::fake()->createWithContent('rec.saf', "SESAME ASCII data format (saf) v. 1\nSAMP_FREQ = 100\n####------\n1 2 3\n")];
        $uploads = $this->post("/api/projects/{$project['id']}/uploads", ['files' => $files])->assertCreated()->json();
        $this->assertSame('saf', $uploads[0]['inspect']['format']);
        $rec = $this->postJson("/api/projects/{$project['id']}/recordings", [
            'name' => 'SAF rec', 'upload_ids' => [$uploads[0]['upload_id']],
            'import' => ['format' => 'saf', 'saf' => ['units' => 'counts'], 'metadata' => ['is_synthetic' => true]],
        ])->assertCreated()->json();
        $this->assertSame('saf', $rec['format']);
        $call = collect($this->engine->calls)->last(fn ($c) => $c['method'] === 'importRecording');
        $this->assertSame('saf', $call['payload']['format']);
        $this->assertSame(['units' => 'counts'], $call['payload']['saf']);

        $files = [UploadedFile::fake()->createWithContent('rec.gse', 'WID2 fake')];
        $uploads = $this->post("/api/projects/{$project['id']}/uploads", ['files' => $files])->assertCreated()->json();
        $this->assertSame('seismic', $uploads[0]['inspect']['format']);
        $rec = $this->postJson("/api/projects/{$project['id']}/recordings", [
            'name' => 'GSE rec', 'upload_ids' => [$uploads[0]['upload_id']],
            'import' => ['format' => 'seismic', 'mseed' => ['n' => 'XX.SYN..HHN', 'e' => 'XX.SYN..HHE', 'z' => 'XX.SYN..HHZ'], 'metadata' => []],
        ])->assertCreated()->json();
        $this->assertSame('seismic', $rec['format']);
        $call = collect($this->engine->calls)->last(fn ($c) => $c['method'] === 'importRecording');
        $this->assertSame('seismic', $call['payload']['format']);
        $this->assertSame('XX.SYN..HHZ', $call['payload']['mseed']['z']);

        $this->postJson("/api/projects/{$project['id']}/recordings", ['name' => 'x', 'upload_ids' => [$uploads[0]['upload_id']], 'import' => ['format' => 'sac']])->assertStatus(422);
    }

    public function test_windows_endpoint_passes_window_modes_and_custom_windows(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $res = $this->postJson("/api/recordings/{$recording['id']}/windows", ['params' => ['windows' => ['mode' => 'custom', 'custom' => [[5, 35], [40, 100]]]]])->assertOk()->json();
        $this->assertSame('custom', $res['mode']);
        $this->assertCount(2, $res['windows']);
        $this->assertEquals(30.0, $res['windows'][0]['length_s']);
        $this->assertSame(1, $res['windows'][1]['color_index']);
    }
}
