<?php

namespace App\Services\Projects;

use App\Models\ActivityLog;
use App\Models\ProcessingRun;
use App\Models\Recording;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Support\Facades\File;
use Illuminate\Validation\ValidationException;

class RunService
{
    public function __construct(
        private readonly EngineClientInterface $engine,
        private readonly ProjectStorage $storage,
    ) {}

    public function create(Recording $recording, string $name, array $steps): ProcessingRun
    {
        if ($recording->status !== 'ready' || ! $recording->canonical_path) {
            throw ValidationException::withMessages(['recording' => 'Recording is not ready for processing.']);
        }

        $run = new ProcessingRun([
            'project_id' => $recording->project_id,
            'recording_id' => $recording->id,
            'name' => $name,
            'steps' => array_values($steps),
            'status' => 'queued',
            'progress' => 0,
        ]);
        $run->save();

        $dir = $this->storage->runDir($recording->project, $run->ulid);
        File::ensureDirectoryExists($dir);
        $output = $dir.'/processed.npz';
        File::put($dir.'/steps.json', json_encode(['steps' => $run->steps, 'created_at' => now()->toIso8601String()], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

        $job = $this->engine->processingRun([
            'input_path' => $recording->canonical_path,
            'output_path' => $output,
            'steps' => $run->steps,
        ]);

        $run->update([
            'output_path' => $output,
            'job_id' => $job['id'] ?? null,
            'status' => $job['status'] ?? 'queued',
            'progress' => (float) ($job['progress'] ?? 0),
        ]);

        ActivityLog::record($recording->project_id, 'run.created', $run, ['name' => $name, 'steps' => count($steps), 'recording' => $recording->ulid]);

        return $run;
    }

    public function delete(ProcessingRun $run): void
    {
        if ($run->isActive() && $run->job_id) {
            try {
                $this->engine->cancelJob($run->job_id);
            } catch (\Throwable) {
            }
        }
        $dir = $this->storage->runDir($run->project, $run->ulid);
        if (is_dir($dir)) {
            File::deleteDirectory($dir);
        }
        ActivityLog::record($run->project_id, 'run.deleted', $run, ['name' => $run->name]);
        $run->delete();
    }
}
