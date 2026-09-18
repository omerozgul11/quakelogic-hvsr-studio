<?php

namespace Tests\Feature;

use Tests\TestCase;

class ExportsAndReportTest extends TestCase
{
    public function test_csv_and_json_exports_download(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->finishAnalysis($analysis['id']);

        foreach (['hvsr-csv', 'windows-csv', 'spectra-csv', 'summary-csv', 'summary-json', 'config-json', 'azimuthal-csv'] as $kind) {
            $response = $this->get("/api/analyses/{$analysis['id']}/exports/{$kind}");
            $response->assertOk();
            $this->assertStringContainsString('attachment', $response->headers->get('content-disposition'));
        }
        $this->assertStringContainsString('Site_A_HVSR_test_hvsr_mean.csv', $this->get("/api/analyses/{$analysis['id']}/exports/hvsr-csv")->headers->get('content-disposition'));
        $this->getJson("/api/analyses/{$analysis['id']}/exports/nope")->assertNotFound();

        unlink($analysis['result_dir'].'/exports/azimuthal.csv');
        $this->getJson("/api/analyses/{$analysis['id']}/exports/azimuthal-csv")->assertNotFound();
    }

    public function test_exports_require_finished_analysis(): void
    {
        $this->engine->pollsToFinish = 3;
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->getJson("/api/analyses/{$analysis['id']}/exports/hvsr-csv")->assertStatus(409);
    }

    public function test_figure_export(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->finishAnalysis($analysis['id']);

        $response = $this->get("/api/analyses/{$analysis['id']}/figure?figure=hvsr&format=svg");
        $response->assertOk();
        $this->assertFileExists($analysis['result_dir'].'/exports/hvsr.svg');
        $call = collect($this->engine->calls)->firstWhere('method', 'exportFigure');
        $this->assertSame('svg', $call['payload']['format']);
        $this->assertSame($analysis['result_dir'], $call['payload']['analysis_dir']);

        $this->getJson("/api/analyses/{$analysis['id']}/figure?figure=hvsr&format=gif")->assertStatus(422);
        $this->getJson("/api/analyses/{$analysis['id']}/figure?figure=pie&format=png")->assertStatus(422);
    }

    public function test_report_job_and_download(): void
    {
        $this->engine->pollsToFinish = 2;
        $project = $this->createProject();
        $station = $this->postJson("/api/projects/{$project['id']}/stations", ['code' => 'ST1', 'name' => 'Station'])->json();
        $recording = $this->importRecording($project['id'], ['station_id' => $station['id']]);
        $analysis = $this->createAnalysis($recording['id']);
        $this->getJson("/api/analyses/{$analysis['id']}");
        $this->getJson("/api/analyses/{$analysis['id']}")->assertJsonPath('status', 'done');

        $this->get("/api/analyses/{$analysis['id']}/report")->assertNotFound();

        $created = $this->postJson("/api/analyses/{$analysis['id']}/report")->assertStatus(202)->json();
        $this->assertSame('queued', $created['job']['status']);
        $call = collect($this->engine->calls)->firstWhere('method', 'exportReport');
        $this->assertSame('ST1', $call['payload']['context']['station']['code']);
        $this->assertSame('1.0.0', $call['payload']['context']['app_version']);
        $this->assertCount(1, $call['payload']['context']['source_files']);
        $this->assertSame(64, strlen($call['payload']['context']['source_files'][0]['sha256']));

        $this->engine->pollsToFinish = 3;
        $this->postJson("/api/analyses/{$analysis['id']}/report")->assertStatus(409); // duplicate request (polls once)
        $this->get("/api/analyses/{$analysis['id']}/report")->assertStatus(409);     // still running (second poll)
        $response = $this->get("/api/analyses/{$analysis['id']}/report");             // done (third poll)
        $response->assertOk();
        $this->assertStringContainsString('report.pdf', $response->headers->get('content-disposition'));
        $this->getJson("/api/analyses/{$analysis['id']}?include=none")->assertJsonPath('report_ready', true)->assertJsonPath('report_status', 'done');
    }
}
