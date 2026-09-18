<?php

namespace App\Services\Projects;

use App\Http\Controllers\Api\SurveyController;
use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Models\ProcessingRun;
use App\Models\Recording;
use App\Models\Setting;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Support\Facades\File;
use Illuminate\Validation\ValidationException;

class AnalysisService
{
    public function __construct(
        private readonly EngineClientInterface $engine,
        private readonly ProjectStorage $storage,
    ) {}

    public function create(Recording $recording, array $data): Analysis
    {
        if ($recording->status !== 'ready') {
            throw ValidationException::withMessages(['recording' => 'Recording is not ready for analysis.']);
        }

        $run = null;
        if (! empty($data['run_id'])) {
            $run = ProcessingRun::query()->where('ulid', $data['run_id'])->where('recording_id', $recording->id)->first();
            if (! $run) {
                throw ValidationException::withMessages(['run_id' => 'Unknown processing run for this recording.']);
            }
            if ($run->status !== 'done' || ! $run->output_path) {
                throw ValidationException::withMessages(['run_id' => 'Processing run has not finished successfully.']);
            }
        }

        $analysis = new Analysis([
            'project_id' => $recording->project_id,
            'recording_id' => $recording->id,
            'processing_run_id' => $run?->id,
            'name' => $data['name'] ?? ('HVSR '.now()->format('Y-m-d H:i')),
            'params' => $data['params'] ?? [],
            'window_overrides' => $data['window_overrides'] ?? [],
            'manual_peak' => $data['manual_peak'] ?? null,
            'random_seed' => $data['random_seed'] ?? random_int(1, 2_000_000_000),
            'status' => 'queued',
            'progress' => 0,
        ]);
        $analysis->save();

        $this->submit($analysis);
        ActivityLog::record($recording->project_id, 'analysis.created', $analysis, ['name' => $analysis->name, 'recording' => $recording->ulid]);

        return $analysis;
    }

    public function submit(Analysis $analysis): Analysis
    {
        $recording = $analysis->recording;
        $run = $analysis->run;
        $dir = $this->storage->analysisDir($recording->project, $analysis->ulid);
        File::ensureDirectoryExists($dir);

        $job = $this->engine->hvsrAnalyze([
            'input_path' => $run?->output_path ?: $recording->canonical_path,
            'output_dir' => $dir,
            'params' => $analysis->params ?? [],
            'window_overrides' => (object) ($analysis->window_overrides ?? []),
            'manual_peak' => $analysis->manual_peak,
            'random_seed' => $analysis->random_seed,
        ]);

        $analysis->update([
            'result_dir' => $dir,
            'job_id' => $job['id'] ?? null,
            'status' => $job['status'] ?? 'queued',
            'progress' => (float) ($job['progress'] ?? 0),
            'error' => null,
            'summary' => null,
        ]);

        return $analysis;
    }

    public function rerun(Analysis $analysis): Analysis
    {
        if ($analysis->isActive()) {
            throw ValidationException::withMessages(['status' => 'Analysis is still running.']);
        }
        ActivityLog::record($analysis->project_id, 'analysis.rerun', $analysis, ['random_seed' => $analysis->random_seed]);

        return $this->submit($analysis);
    }

    public function selectPeak(Analysis $analysis, ?float $frequency): array
    {
        if ($analysis->status !== 'done') {
            throw ValidationException::withMessages(['status' => 'Analysis has not finished.']);
        }
        $result = $this->engine->selectPeak($analysis->result_dir, $frequency);
        $summary = $this->engine->analysisSummary($analysis->result_dir);
        $analysis->update([
            'manual_peak' => $frequency === null ? null : ['frequency' => $frequency],
            'summary' => $summary,
        ]);
        ActivityLog::record($analysis->project_id, 'analysis.peak_selected', $analysis, ['frequency' => $frequency]);

        return $result;
    }

    public function reportContext(Analysis $analysis): array
    {
        $recording = $analysis->recording;
        $project = $recording->project;
        $station = $recording->station;
        $run = $analysis->run;

        return [
            'app_version' => config('hvsr.app_version'),
            'unit_system' => Setting::get('unit_system', 'metric'),
            'project' => ['id' => $project->ulid, 'name' => $project->name, 'description' => $project->description],
            'station' => $station ? [
                'code' => $station->code, 'name' => $station->name, 'latitude' => $station->latitude, 'longitude' => $station->longitude,
                'elevation' => $station->elevation, 'orientation_deg' => $station->orientation_deg, 'notes' => $station->notes,
            ] : null,
            'recording' => [
                'id' => $recording->ulid, 'name' => $recording->name, 'format' => $recording->format, 'sample_rate' => $recording->sample_rate,
                'start_time' => $recording->start_time, 'duration_s' => $recording->duration_s, 'n_samples' => $recording->n_samples,
                'units' => $recording->units, 'unit_kind' => $recording->unit_kind, 'is_synthetic' => $recording->is_synthetic,
                'validation' => $recording->validation, 'notes' => $recording->notes,
            ],
            'source_files' => $recording->files->map(fn ($f) => [
                'name' => $f->original_name, 'role' => $f->role, 'size_bytes' => $f->size_bytes, 'sha256' => $f->sha256,
            ])->values()->all(),
            'processing_run' => $run ? ['id' => $run->ulid, 'name' => $run->name] : null,
            'processing_steps' => $run ? ($run->applied ?: $run->steps ?: []) : [],
            'analysis' => ['id' => $analysis->ulid, 'name' => $analysis->name, 'created_at' => $analysis->created_at?->toIso8601String(), 'random_seed' => $analysis->random_seed],
            'survey' => $this->surveyContext($analysis),
        ];
    }

    /** Survey block with absolute photo paths (null when nothing was entered). */
    private function surveyContext(Analysis $analysis): ?array
    {
        $survey = SurveyController::normalise($analysis->survey);
        $hasValue = collect($survey)->except('photos', 'datum')->contains(fn ($v) => $v !== null && $v !== '');
        if (! $hasValue && ! $survey['photos']) {
            return null;
        }
        $dir = $analysis->result_dir ?: $this->storage->analysisDir($analysis->recording->project, $analysis->ulid);
        $survey['photos'] = array_values(array_filter(array_map(function ($p) use ($dir) {
            $path = $dir.'/'.$p['file'];

            return is_file($path) ? ['path' => $path, 'file' => $p['file'], 'caption' => $p['caption'] ?? ''] : null;
        }, $survey['photos'])));

        return $survey;
    }
}
