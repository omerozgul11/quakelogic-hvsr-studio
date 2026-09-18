<?php

namespace Tests\Feature;

use Tests\TestCase;

class CompareTest extends TestCase
{
    public function test_compare_returns_curves_and_errors_per_analysis(): void
    {
        $this->engine->pollsToFinish = 1;
        $project = $this->createProject();
        $a = $this->importRecording($project['id'], ['name' => 'A']);
        $b = $this->importRecording($project['id'], ['name' => 'B']);
        $an1 = $this->createAnalysis($a['id']);
        $an2 = $this->createAnalysis($b['id']);
        $this->finishAnalysis($an1['id']);
        $this->engine->pollsToFinish = 10; // keep an2 running

        $rows = $this->postJson("/api/projects/{$project['id']}/compare", ['analysis_ids' => [$an1['id'], $an2['id'], '01HZZZZZZZZZZZZZZZZZZZZZZZ']])->assertOk()->json();
        $this->assertCount(3, $rows);
        $this->assertSame('A', $rows[0]['recording_name']);
        $this->assertCount(7, $rows[0]['curve']);
        $this->assertCount(7, $rows[0]['lower']);
        $this->assertSame(2.5, $rows[0]['peak']['frequency']);
        $this->assertSame('geometric', $rows[0]['mean_method']);
        $this->assertArrayHasKey('error', $rows[1]);
        $this->assertSame('Unknown analysis', $rows[2]['error']);
    }
}
