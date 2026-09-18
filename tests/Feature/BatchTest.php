<?php

namespace Tests\Feature;

use App\Models\Analysis;
use App\Models\ProcessingRun;
use Database\Seeders\PresetSeeder;
use Tests\TestCase;

class BatchTest extends TestCase
{
    private function setupProjectWithRecordings(int $n = 3): array
    {
        $this->seed(PresetSeeder::class);
        $project = $this->createProject();
        $recordings = [];
        for ($i = 0; $i < $n; $i++) {
            $recordings[] = $this->importRecording($project['id'], ['name' => 'Rec '.$i]);
        }
        $preset = collect($this->getJson("/api/projects/{$project['id']}/presets")->json())->firstWhere('name', 'Standard ambient noise (60 s, KO 40)');

        return [$project, $recordings, $preset];
    }

    public function test_batch_runs_items_sequentially_and_continues_after_failure(): void
    {
        $this->engine->pollsToFinish = 2;
        [$project, $recordings, $preset] = $this->setupProjectWithRecordings(3);

        $batch = $this->postJson("/api/projects/{$project['id']}/batches", [
            'name' => 'Nightly', 'preset_id' => $preset['id'], 'recording_ids' => array_column($recordings, 'id'), 'run_steps' => true,
        ])->assertCreated()->json();
        $this->assertSame('running', $batch['status']);
        $this->assertCount(3, $batch['items']);
        $this->assertSame('running', $batch['items'][0]['status']);
        $this->assertNotNull($batch['items'][0]['run_id']);
        $this->assertSame('queued', $batch['items'][1]['status']);

        // Make the second item's run fail once it is submitted.
        $batch = $this->getJson("/api/batches/{$batch['id']}")->json(); // item0: run done -> analysis submitted
        $this->assertNotNull($batch['items'][0]['analysis_id']);
        $batch = $this->getJson("/api/batches/{$batch['id']}")->json(); // item0 analysis done -> item1 run submitted
        $this->assertSame('done', $batch['items'][0]['status']);
        $this->assertSame('running', $batch['items'][1]['status']);
        $run1 = ProcessingRun::query()->where('ulid', $batch['items'][1]['run_id'])->first();
        $this->engine->failJobs[] = $run1->job_id;

        $batch = $this->getJson("/api/batches/{$batch['id']}")->json(); // item1 fails, item2 starts
        $this->assertSame('failed', $batch['items'][1]['status']);
        $this->assertStringContainsString('Simulated', $batch['items'][1]['error']);
        $this->assertSame('running', $batch['items'][2]['status']);

        $batch = $this->getJson("/api/batches/{$batch['id']}")->json();
        $batch = $this->getJson("/api/batches/{$batch['id']}")->json();
        $this->assertSame('done', $batch['items'][2]['status']);
        $this->assertSame('done', $batch['status']);
        $this->assertSame(2, $batch['counts']['done']);
        $this->assertSame(1, $batch['counts']['failed']);
        $this->assertSame(2, Analysis::query()->count());
        $this->assertSame(2.5, $batch['items'][2]['summary']['peaks']['selected']['frequency']);
        $this->assertDatabaseHas('activity_log', ['action' => 'batch.item_failed']);
        $this->assertDatabaseHas('activity_log', ['action' => 'batch.completed']);

        $this->getJson("/api/projects/{$project['id']}")->assertJsonPath('batches.0.id', $batch['id']);
    }

    public function test_batch_without_steps_submits_analysis_directly(): void
    {
        [$project, $recordings, $preset] = $this->setupProjectWithRecordings(1);
        $batch = $this->postJson("/api/projects/{$project['id']}/batches", [
            'name' => 'Analysis only', 'preset_id' => $preset['id'], 'recording_ids' => [$recordings[0]['id']], 'run_steps' => false,
        ])->assertCreated()->json();
        $this->assertNull($batch['items'][0]['run_id']);
        $this->assertNotNull($batch['items'][0]['analysis_id']);
        $call = collect($this->engine->calls)->firstWhere('method', 'hvsrAnalyze');
        $this->assertSame(60, $call['payload']['params']['window_length_s']);
        $batch = $this->getJson("/api/batches/{$batch['id']}")->json();
        $this->assertSame('done', $batch['status']);
    }

    public function test_batch_cancel(): void
    {
        $this->engine->pollsToFinish = 10;
        [$project, $recordings, $preset] = $this->setupProjectWithRecordings(2);
        $batch = $this->postJson("/api/projects/{$project['id']}/batches", [
            'name' => 'Cancel me', 'preset_id' => $preset['id'], 'recording_ids' => array_column($recordings, 'id'),
        ])->json();
        $batch = $this->postJson("/api/batches/{$batch['id']}/cancel")->assertOk()->json();
        $this->assertSame('cancelled', $batch['status']);
        $this->assertSame(['cancelled', 'cancelled'], array_column($batch['items'], 'status'));
        $this->assertSame('cancelled', ProcessingRun::query()->first()->status);
        $this->getJson("/api/batches/{$batch['id']}")->assertJsonPath('status', 'cancelled');
    }

    public function test_batch_validation(): void
    {
        [$project] = $this->setupProjectWithRecordings(1);
        $this->postJson("/api/projects/{$project['id']}/batches", ['name' => 'x', 'recording_ids' => ['01HZZZZZZZZZZZZZZZZZZZZZZZ']])->assertStatus(422);
        $this->postJson("/api/projects/{$project['id']}/batches", ['name' => 'x', 'recording_ids' => []])->assertStatus(422);
    }
}
