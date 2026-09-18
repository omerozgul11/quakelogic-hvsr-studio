<?php

namespace Tests;

use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\FakeEngineClient;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Foundation\Testing\TestCase as BaseTestCase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\File;
use Illuminate\Testing\TestResponse;

abstract class TestCase extends BaseTestCase
{
    use RefreshDatabase;

    protected FakeEngineClient $engine;

    protected string $dataDir;

    protected function setUp(): void
    {
        parent::setUp();

        $this->dataDir = sys_get_temp_dir().'/hvsr-tests-'.uniqid();
        File::ensureDirectoryExists($this->dataDir.'/projects');
        config(['hvsr.data_dir' => $this->dataDir, 'hvsr.projects_dir' => $this->dataDir.'/projects']);

        $this->engine = new FakeEngineClient;
        $this->app->instance(EngineClientInterface::class, $this->engine);
    }

    protected function tearDown(): void
    {
        if (isset($this->dataDir) && is_dir($this->dataDir)) {
            File::deleteDirectory($this->dataDir);
        }
        parent::tearDown();
    }

    protected function createProject(string $name = 'Test Project'): array
    {
        return $this->postJson('/api/projects', ['name' => $name])->assertCreated()->json();
    }

    protected function uploadFiles(string $projectId, array $names = ['site.csv']): array
    {
        $files = [];
        foreach ($names as $name) {
            $files[] = UploadedFile::fake()->createWithContent($name, "t,N,E,Z\n0,1,1,1\n0.01,2,2,2\n");
        }

        return $this->post("/api/projects/{$projectId}/uploads", ['files' => $files])->assertCreated()->json();
    }

    protected function importRecording(string $projectId, array $overrides = []): array
    {
        $uploads = $this->uploadFiles($projectId);

        return $this->postJson("/api/projects/{$projectId}/recordings", array_merge([
            'name' => 'Site A',
            'upload_ids' => [$uploads[0]['upload_id']],
            'import' => [
                'format' => 'ascii',
                'ascii' => [
                    'delimiter' => ',', 'decimal' => '.', 'header_rows' => 1, 'comment_prefix' => '#',
                    'columns' => ['n' => 1, 'e' => 2, 'z' => 3],
                    'time' => ['mode' => 'seconds_column', 'column' => 0, 'sample_rate' => null, 'datetime_format' => null],
                    'start_time' => null, 'units' => 'counts', 'unit_kind' => 'raw', 'scale_factor' => 1.0,
                ],
                'metadata' => ['station' => 'SYN1', 'network' => 'XX', 'is_synthetic' => true],
            ],
        ], $overrides))->assertCreated()->json();
    }

    protected function createAnalysis(string $recordingId, array $overrides = []): array
    {
        return $this->postJson("/api/recordings/{$recordingId}/analyses", array_merge([
            'name' => 'HVSR test',
            'params' => ['window_length_s' => 60, 'overlap' => 0.5, 'freq_min' => 0.2, 'freq_max' => 30],
        ], $overrides))->assertCreated()->json();
    }

    protected function finishAnalysis(string $analysisId): TestResponse
    {
        return $this->getJson("/api/analyses/{$analysisId}")->assertOk();
    }
}
