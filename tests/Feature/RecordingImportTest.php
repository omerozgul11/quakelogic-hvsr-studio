<?php

namespace Tests\Feature;

use App\Models\Recording;
use App\Models\Upload;
use Tests\TestCase;

class RecordingImportTest extends TestCase
{
    public function test_upload_stages_files_and_inspects_them(): void
    {
        $project = $this->createProject();
        $uploads = $this->uploadFiles($project['id'], ['a.csv', 'b.mseed']);
        $this->assertCount(2, $uploads);
        $this->assertSame('ascii', $uploads[0]['inspect']['format']);
        $this->assertSame('mseed', $uploads[1]['inspect']['format']);
        $this->assertSame(64, strlen($uploads[0]['sha256']));
        $upload = Upload::query()->where('ulid', $uploads[0]['upload_id'])->first();
        $this->assertFileExists($upload->stored_path);
        $this->assertStringStartsWith($this->dataDir.'/projects/', $upload->stored_path);
    }

    public function test_import_success_stores_metadata_files_and_moves_sources(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);

        $this->assertSame('ready', $recording['status']);
        $this->assertEquals(100.0, $recording['sample_rate']);
        $this->assertEquals(600.0, $recording['duration_s']);
        $this->assertTrue($recording['is_synthetic']);
        $this->assertCount(1, $recording['files']);
        $this->assertSame('site.csv', $recording['files'][0]['name']);
        $this->assertSame(64, strlen($recording['files'][0]['sha256']));
        $this->assertFalse($recording['validation']['blocking']);

        $model = Recording::query()->where('ulid', $recording['id'])->first();
        $this->assertFileExists($model->canonical_path);
        $this->assertFileExists($model->files->first()->stored_path);
        $this->assertStringContainsString('/sources/'.$model->ulid.'/', $model->files->first()->stored_path);

        $call = collect($this->engine->calls)->firstWhere('method', 'importRecording');
        $this->assertSame($model->canonical_path, $call['payload']['output_path']);
        $this->assertSame('SYN1', $call['payload']['metadata']['station']);
        $this->assertTrue(Upload::query()->first()->consumed);

        $this->getJson("/api/recordings/{$recording['id']}")->assertOk()->assertJsonPath('name', 'Site A')->assertJsonStructure(['runs', 'analyses']);
    }

    public function test_blocking_validation_returns_422_and_cleans_up(): void
    {
        $this->engine->importBlocking = true;
        $project = $this->createProject();
        $uploads = $this->uploadFiles($project['id']);

        $response = $this->postJson("/api/projects/{$project['id']}/recordings", [
            'name' => 'Bad', 'upload_ids' => [$uploads[0]['upload_id']],
            'import' => ['format' => 'ascii', 'ascii' => ['columns' => ['n' => 1, 'e' => 2, 'z' => 3], 'time' => ['mode' => 'sample_rate', 'sample_rate' => 100]]],
        ]);
        $response->assertStatus(422)->assertJsonPath('validation.blocking', true)->assertJsonPath('validation.issues.0.code', 'nan_values');
        $this->assertSame(0, Recording::query()->count());
        $this->assertEmpty(glob($this->dataDir.'/projects/*/sources/*'));
    }

    public function test_separate_component_files_carry_roles(): void
    {
        $project = $this->createProject();
        $uploads = $this->uploadFiles($project['id'], ['n.txt', 'e.txt', 'z.txt']);
        $ids = array_column($uploads, 'upload_id');
        $recording = $this->postJson("/api/projects/{$project['id']}/recordings", [
            'name' => 'Split', 'upload_ids' => $ids,
            'import' => ['format' => 'ascii', 'roles' => [$ids[0] => 'n', $ids[1] => 'e', $ids[2] => 'z'],
                'ascii' => ['columns' => ['n' => 0, 'e' => 0, 'z' => 0], 'time' => ['mode' => 'sample_rate', 'sample_rate' => 200]]],
        ])->assertCreated()->json();
        $this->assertSame(['n', 'e', 'z'], array_column($recording['files'], 'role'));
        $call = collect($this->engine->calls)->firstWhere('method', 'importRecording');
        $this->assertSame(['n', 'e', 'z'], array_column($call['payload']['sources'], 'role'));
    }

    public function test_unknown_or_reused_uploads_are_rejected(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $usedUpload = Upload::query()->first()->ulid;
        $this->postJson("/api/projects/{$project['id']}/recordings", [
            'name' => 'Again', 'upload_ids' => [$usedUpload], 'import' => ['format' => 'ascii'],
        ])->assertStatus(422)->assertJsonValidationErrors(['upload_ids']);
    }

    public function test_update_and_delete_recording(): void
    {
        $project = $this->createProject();
        $station = $this->postJson("/api/projects/{$project['id']}/stations", ['code' => 'S1'])->json();
        $recording = $this->importRecording($project['id']);
        $this->putJson("/api/recordings/{$recording['id']}", ['name' => 'Renamed', 'station_id' => $station['id']])
            ->assertOk()->assertJsonPath('name', 'Renamed')->assertJsonPath('station.code', 'S1');
        $model = Recording::query()->where('ulid', $recording['id'])->first();
        $path = $model->canonical_path;
        $this->deleteJson("/api/recordings/{$recording['id']}")->assertOk();
        $this->assertFileDoesNotExist($path);
        $this->assertDirectoryDoesNotExist($this->dataDir.'/projects/'.$project['slug'].'/sources/'.$model->ulid);
        $this->getJson("/api/recordings/{$recording['id']}")->assertNotFound();
    }

    public function test_data_proxy_uses_canonical_or_run_output(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $this->getJson("/api/recordings/{$recording['id']}/data?t_start=0&t_end=10&max_points=500&components=n,z")
            ->assertOk()->assertJsonPath('downsampled', true)->assertJsonStructure(['components' => ['n' => ['t', 'v']]]);
        $call = collect($this->engine->calls)->firstWhere('method', 'recordingData');
        $this->assertSame(['n', 'z'], $call['payload']['components']);
        $this->assertSame(500, $call['payload']['max_points']);
        $this->assertStringEndsWith('.npz', $call['payload']['path']);
        $this->getJson("/api/recordings/{$recording['id']}/data?run=01HZZZZZZZZZZZZZZZZZZZZZZZ")->assertStatus(422);
    }

    public function test_spectra_windows_and_preview_proxies(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);

        $this->postJson("/api/recordings/{$recording['id']}/spectra", ['kind' => 'fas', 'window_length_s' => 60])->assertOk()->assertJsonStructure(['frequency', 'components']);
        $this->postJson("/api/recordings/{$recording['id']}/spectra", ['kind' => 'nope'])->assertStatus(422);

        $this->postJson("/api/recordings/{$recording['id']}/processing/preview", [
            'steps' => [['op' => 'demean', 'params' => []], ['op' => 'filter', 'params' => ['kind' => 'highpass', 'freq_low' => 0.5]]],
            't_start' => 0, 't_end' => 60,
        ])->assertOk()->assertJsonStructure(['raw', 'processed', 'warnings', 'applied', 'fs_out']);

        $this->postJson("/api/recordings/{$recording['id']}/windows", [
            'params' => ['window_length_s' => 60, 'overlap' => 0.5],
            'window_overrides' => ['2' => ['accepted' => true, 'reason' => 'manual']],
        ])->assertOk()->assertJsonPath('counts.accepted', 5)->assertJsonPath('windows.2.reason', 'manual');
    }
}
