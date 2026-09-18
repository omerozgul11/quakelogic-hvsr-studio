<?php

namespace Tests\Feature;

use App\Models\Analysis;
use App\Services\Projects\AnalysisService;
use Database\Seeders\PresetSeeder;
use Tests\TestCase;

class ProjectApiTest extends TestCase
{
    public function test_project_crud_and_folder_layout(): void
    {
        $project = $this->createProject('My Site Survey');
        $this->assertSame('my-site-survey', $project['slug']);
        $this->assertDirectoryExists($this->dataDir.'/projects/my-site-survey/traces');
        $this->assertFileExists($this->dataDir.'/projects/my-site-survey/project.json');

        $this->getJson('/api/projects')->assertOk()->assertJsonCount(1)->assertJsonPath('0.id', $project['id']);

        $this->putJson("/api/projects/{$project['id']}", ['name' => 'Renamed', 'description' => 'desc'])
            ->assertOk()->assertJsonPath('name', 'Renamed')->assertJsonPath('description', 'desc');

        $this->getJson("/api/projects/{$project['id']}")->assertOk()
            ->assertJsonStructure(['id', 'name', 'stations', 'recordings', 'presets', 'batches', 'counts']);

        $this->getJson("/api/projects/{$project['id']}/history")->assertOk()->assertJsonPath('0.action', 'project.updated');

        $this->deleteJson("/api/projects/{$project['id']}")->assertOk()->assertJson(['deleted' => true]);
        $this->assertDirectoryDoesNotExist($this->dataDir.'/projects/my-site-survey');
        $this->getJson("/api/projects/{$project['id']}")->assertNotFound();
    }

    public function test_duplicate_names_get_unique_slugs(): void
    {
        $a = $this->createProject('Same');
        $b = $this->createProject('Same');
        $this->assertSame('same', $a['slug']);
        $this->assertSame('same-2', $b['slug']);
    }

    public function test_validation_errors(): void
    {
        $this->postJson('/api/projects', [])->assertStatus(422)->assertJsonValidationErrors(['name']);
    }

    public function test_project_show_includes_builtin_presets(): void
    {
        $this->seed(PresetSeeder::class);
        $project = $this->createProject();
        $presets = $this->getJson("/api/projects/{$project['id']}")->json('presets');
        $this->assertCount(3, $presets);
        $this->assertTrue($presets[0]['builtin']);
    }

    public function test_app_status_and_settings(): void
    {
        $this->getJson('/api/app/status')->assertOk()->assertJsonPath('engine.status', 'ok')->assertJsonPath('app_version', '1.0.0');

        $this->putJson('/api/settings', ['theme_default' => 'dark', 'plot_max_points' => 6000])->assertOk()
            ->assertJsonPath('theme_default', 'dark')->assertJsonPath('plot_max_points', 6000);
        $this->getJson('/api/settings')->assertOk()->assertJsonPath('theme_default', 'dark')->assertJsonPath('engine_url', config('hvsr.engine_url'));
        $this->putJson('/api/settings', ['theme_default' => 'purple'])->assertStatus(422);
    }

    public function test_unit_system_setting_is_stored_and_reaches_the_report_context(): void
    {
        $this->getJson('/api/settings')->assertOk()->assertJsonPath('unit_system', 'metric');
        $this->putJson('/api/settings', ['unit_system' => 'us'])->assertOk()->assertJsonPath('unit_system', 'us');
        $this->putJson('/api/settings', ['unit_system' => 'imperial'])->assertStatus(422);

        $project = $this->createProject('Units');
        $station = $this->postJson("/api/projects/{$project['id']}/stations", ['code' => 'STA1', 'elevation' => 12.5])->assertCreated()->json();
        $recording = $this->importRecording($project['id'], ['station_id' => $station['id']]);
        $analysisJson = $this->createAnalysis($recording['id']);
        $analysis = Analysis::where('ulid', $analysisJson['id'])->firstOrFail();

        $context = app(AnalysisService::class)->reportContext($analysis);
        $this->assertSame('us', $context['unit_system']);
        $this->assertSame(12.5, (float) $context['station']['elevation']);
    }

    public function test_engine_down_gives_503(): void
    {
        $this->engine->down = true;
        $this->getJson('/api/app/status')->assertOk()->assertJsonPath('engine.status', 'down');
        $this->getJson('/api/jobs/abc')->assertStatus(503)->assertJsonPath('message', 'Processing engine is not running');
    }

    public function test_spa_catch_all_serves_app_view(): void
    {
        $this->withoutVite();
        $this->get('/projects/abc')->assertOk()->assertSee('QuakeLogic HVSR Studio');
        $this->get('/api/does-not-exist')->assertNotFound();
    }
}
