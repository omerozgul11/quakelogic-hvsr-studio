<?php

namespace Tests\Feature;

use App\Models\ProcessingRun;
use Tests\TestCase;

class ProcessingRunTest extends TestCase
{
    public function test_run_create_and_status_sync(): void
    {
        $this->engine->pollsToFinish = 2;
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);

        $steps = [['op' => 'demean', 'enabled' => true, 'params' => []], ['op' => 'filter', 'enabled' => true, 'params' => ['kind' => 'bandpass', 'freq_low' => 0.2, 'freq_high' => 20, 'order' => 4, 'zero_phase' => true]]];
        $created = $this->postJson("/api/recordings/{$recording['id']}/runs", ['name' => 'Clean', 'steps' => $steps])->assertCreated()->json();
        $run = $created['run'];
        $this->assertSame('queued', $run['status']);
        $this->assertNotNull($run['job_id']);
        $this->assertFileExists($this->dataDir.'/projects/'.$project['slug'].'/runs/'.$run['id'].'/steps.json');

        $first = $this->getJson("/api/runs/{$run['id']}")->assertOk()->json();
        $this->assertSame('running', $first['status']);
        $this->assertNotNull($first['job']);

        $second = $this->getJson("/api/runs/{$run['id']}")->assertOk()->json();
        $this->assertSame('done', $second['status']);
        $this->assertEquals(1.0, $second['progress']);
        $this->assertSame($steps, $second['applied']);
        $this->assertFileExists($second['output_path']);
        $this->assertEquals(100.0, $second['meta']['fs']);

        $this->assertDatabaseHas('activity_log', ['action' => 'run.completed']);

        // Recording show lists the run
        $this->getJson("/api/recordings/{$recording['id']}")->assertJsonPath('runs.0.id', $run['id']);

        // Data proxy may now use the run output
        $this->getJson("/api/recordings/{$recording['id']}/data?run={$run['id']}")->assertOk();
        $call = collect($this->engine->calls)->last();
        $this->assertSame($second['output_path'], $call['payload']['path']);

        $this->deleteJson("/api/runs/{$run['id']}")->assertOk();
        $this->assertSame(0, ProcessingRun::query()->count());
        $this->assertDirectoryDoesNotExist(dirname($second['output_path']));
    }

    public function test_run_failure_is_recorded(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $created = $this->postJson("/api/recordings/{$recording['id']}/runs", ['steps' => [['op' => 'demean']]])->assertCreated()->json();
        $this->engine->failJobs[] = $created['run']['job_id'];
        $this->getJson("/api/runs/{$created['run']['id']}")->assertOk()->assertJsonPath('status', 'failed')->assertJsonPath('error', 'Simulated engine failure');
    }

    public function test_run_validation(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $this->postJson("/api/recordings/{$recording['id']}/runs", ['steps' => []])->assertStatus(422);
        $this->postJson("/api/recordings/{$recording['id']}/runs", ['steps' => [['op' => 'explode']]])->assertStatus(422);
    }

    public function test_filter_response_proxy(): void
    {
        $this->postJson('/api/engine/filter-response', ['fs' => 100, 'step' => ['op' => 'filter', 'params' => ['kind' => 'lowpass', 'freq_high' => 20]]])
            ->assertOk()->assertJsonStructure(['frequency', 'magnitude_db', 'phase_deg', 'warnings']);
        $this->postJson('/api/engine/filter-response', ['fs' => 0, 'step' => ['op' => 'filter']])->assertStatus(422);
    }
}
