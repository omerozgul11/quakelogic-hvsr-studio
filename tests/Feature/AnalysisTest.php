<?php

namespace Tests\Feature;

use App\Models\Analysis;
use Tests\TestCase;

class AnalysisTest extends TestCase
{
    public function test_create_poll_and_summary(): void
    {
        $this->engine->pollsToFinish = 2;
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id'], ['random_seed' => 42, 'window_overrides' => ['3' => ['accepted' => false, 'reason' => 'manual']]]);

        $this->assertSame('queued', $analysis['status']);
        $this->assertSame(42, $analysis['random_seed']);
        $this->assertDirectoryExists($analysis['result_dir']);
        $call = collect($this->engine->calls)->firstWhere('method', 'hvsrAnalyze');
        $this->assertSame(42, $call['payload']['random_seed']);
        $this->assertSame($analysis['result_dir'], $call['payload']['output_dir']);
        $this->assertStringEndsWith('.npz', $call['payload']['input_path']);

        $running = $this->getJson("/api/analyses/{$analysis['id']}")->assertOk()->json();
        $this->assertSame('running', $running['status']);
        $this->assertNull($running['result']);
        $this->assertNotNull($running['job']);

        $done = $this->getJson("/api/analyses/{$analysis['id']}")->assertOk()->json();
        $this->assertSame('done', $done['status']);
        $this->assertSame(2.5, $done['summary']['peaks']['selected']['frequency']);
        $this->assertSame('clear', $done['summary']['peaks']['status']);
        $this->assertSame(2.5, $done['result']['peaks']['selected']['frequency']);
        $this->assertCount(7, $done['result']['frequency']);
        $this->assertFileExists($analysis['result_dir'].'/result.json');

        $noResult = $this->getJson("/api/analyses/{$analysis['id']}?include=none")->assertOk()->json();
        $this->assertNull($noResult['result']);

        $this->assertDatabaseHas('activity_log', ['action' => 'analysis.completed']);
        $this->getJson("/api/analyses/{$analysis['id']}/window-curves")->assertOk()->assertJsonStructure(['frequency', 'curves', 'accepted']);
    }

    public function test_random_seed_is_generated_and_rerun_reuses_it(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->assertIsInt($analysis['random_seed']);
        $this->finishAnalysis($analysis['id'])->assertJsonPath('status', 'done');

        $rerun = $this->postJson("/api/analyses/{$analysis['id']}/rerun")->assertOk()->json();
        $this->assertSame('queued', $rerun['status']);
        $this->assertSame($analysis['random_seed'], $rerun['random_seed']);
        $calls = collect($this->engine->calls)->where('method', 'hvsrAnalyze')->values();
        $this->assertCount(2, $calls);
        $this->assertSame($calls[0]['payload']['params'], $calls[1]['payload']['params']);
        $this->assertSame($calls[0]['payload']['random_seed'], $calls[1]['payload']['random_seed']);
    }

    public function test_analysis_with_run_uses_processed_output(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $run = $this->postJson("/api/recordings/{$recording['id']}/runs", ['steps' => [['op' => 'demean']]])->json('run');
        // Not finished yet -> rejected
        $this->postJson("/api/recordings/{$recording['id']}/analyses", ['params' => [], 'run_id' => $run['id']])->assertStatus(422);
        $run = $this->getJson("/api/runs/{$run['id']}")->json();
        $this->assertSame('done', $run['status']);
        $analysis = $this->createAnalysis($recording['id'], ['run_id' => $run['id']]);
        $this->assertSame($run['id'], $analysis['run_id']);
        $call = collect($this->engine->calls)->firstWhere('method', 'hvsrAnalyze');
        $this->assertSame($run['output_path'], $call['payload']['input_path']);
    }

    public function test_failed_job_marks_analysis_failed(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->engine->failJobs[] = $analysis['job_id'];
        $this->getJson("/api/analyses/{$analysis['id']}")->assertOk()->assertJsonPath('status', 'failed')->assertJsonPath('error', 'Simulated engine failure');
        $this->getJson("/api/analyses/{$analysis['id']}/window-curves")->assertStatus(409);
    }

    public function test_select_peak_manual_and_reset(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->finishAnalysis($analysis['id']);

        $manual = $this->postJson("/api/analyses/{$analysis['id']}/select-peak", ['frequency' => 3.1])->assertOk()->json();
        $this->assertSame(['frequency' => 3.1], $manual['manual_peak']);
        $this->assertSame('manual', $manual['result']['peaks']['selected']['source']);
        $this->assertSame(3.1, $manual['summary']['peaks']['selected']['frequency']);

        $auto = $this->postJson("/api/analyses/{$analysis['id']}/select-peak", ['frequency' => null])->assertOk()->json();
        $this->assertNull($auto['manual_peak']);
        $this->assertSame('automatic', $auto['result']['peaks']['selected']['source']);

        $this->postJson("/api/analyses/{$analysis['id']}/select-peak", [])->assertStatus(422);
        $this->postJson("/api/analyses/{$analysis['id']}/select-peak", ['frequency' => -1])->assertStatus(422);
    }

    public function test_cancel_rename_and_delete(): void
    {
        $this->engine->pollsToFinish = 5;
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $analysis = $this->createAnalysis($recording['id']);
        $this->postJson("/api/analyses/{$analysis['id']}/cancel")->assertOk()->assertJsonPath('status', 'cancelled');
        $this->assertSame('cancelled', $this->engine->jobs[$analysis['job_id']]['status']);
        $this->putJson("/api/analyses/{$analysis['id']}", ['name' => 'New name'])->assertOk()->assertJsonPath('name', 'New name');
        $dir = $analysis['result_dir'];
        $this->deleteJson("/api/analyses/{$analysis['id']}")->assertOk();
        $this->assertDirectoryDoesNotExist($dir);
        $this->assertSame(0, Analysis::query()->count());
    }
}
