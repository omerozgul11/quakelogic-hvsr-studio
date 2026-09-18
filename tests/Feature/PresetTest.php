<?php

namespace Tests\Feature;

use Database\Seeders\PresetSeeder;
use Tests\TestCase;

class PresetTest extends TestCase
{
    public function test_presets_crud_and_builtin_protection(): void
    {
        $this->seed(PresetSeeder::class);
        $project = $this->createProject();

        $list = $this->getJson("/api/projects/{$project['id']}/presets")->assertOk()->json();
        $this->assertCount(3, $list);
        $builtin = collect($list)->firstWhere('name', 'Standard ambient noise (60 s, KO 40)');
        $this->assertTrue($builtin['builtin']);
        $this->assertSame(60, $builtin['hvsr_params']['window_length_s']);

        $this->putJson("/api/presets/{$builtin['id']}", ['name' => 'x'])->assertStatus(409);
        $this->deleteJson("/api/presets/{$builtin['id']}")->assertStatus(409);

        $own = $this->postJson("/api/projects/{$project['id']}/presets", [
            'name' => 'Mine', 'steps' => [['op' => 'demean', 'params' => []]], 'hvsr_params' => ['window_length_s' => 40],
        ])->assertCreated()->json();
        $this->assertFalse($own['builtin']);
        $this->putJson("/api/presets/{$own['id']}", ['name' => 'Mine 2', 'hvsr_params' => ['window_length_s' => 45]])
            ->assertOk()->assertJsonPath('name', 'Mine 2')->assertJsonPath('hvsr_params.window_length_s', 45);
        $this->assertCount(4, $this->getJson("/api/projects/{$project['id']}/presets")->json());

        $this->deleteJson("/api/presets/{$own['id']}")->assertOk();
        $this->assertCount(3, $this->getJson("/api/projects/{$project['id']}/presets")->json());

        // Seeder is idempotent
        $this->seed(PresetSeeder::class);
        $this->assertCount(3, $this->getJson("/api/projects/{$project['id']}/presets")->json());
    }
}
