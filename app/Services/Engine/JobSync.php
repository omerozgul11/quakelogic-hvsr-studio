<?php

namespace App\Services\Engine;

use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Models\ProcessingRun;

/**
 * Pulls job state from the engine into the SQLite rows (runs, analyses, reports).
 */
class JobSync
{
    public function __construct(private readonly EngineClientInterface $engine) {}

    public function syncRun(ProcessingRun $run): ProcessingRun
    {
        if (! $run->isActive() || ! $run->job_id) {
            return $run;
        }

        try {
            $job = $this->engine->job($run->job_id);
        } catch (EngineErrorException $e) {
            if ($e->status === 404) {
                $run->update(['status' => 'failed', 'error' => 'Engine job no longer exists (engine restarted?).']);
            }

            return $run;
        }

        $data = ['status' => $job['status'] ?? $run->status, 'progress' => (float) ($job['progress'] ?? $run->progress)];
        if (($job['status'] ?? null) === 'done') {
            $result = $job['result'] ?? [];
            $data += [
                'progress' => 1.0,
                'output_path' => $result['output_path'] ?? $run->output_path,
                'meta' => $result['meta'] ?? null,
                'warnings' => $result['warnings'] ?? [],
                'applied' => $result['applied'] ?? $run->steps,
                'engine_version' => $result['meta']['engine_version'] ?? $run->engine_version,
            ];
            ActivityLog::record($run->project_id, 'run.completed', $run, ['name' => $run->name]);
        } elseif (($job['status'] ?? null) === 'failed') {
            $data['error'] = $job['error'] ?? 'Processing failed.';
            ActivityLog::record($run->project_id, 'run.failed', $run, ['error' => $data['error']]);
        }
        $run->update($data);

        return $run;
    }

    public function syncAnalysis(Analysis $analysis): Analysis
    {
        if ($analysis->isActive() && $analysis->job_id) {
            try {
                $job = $this->engine->job($analysis->job_id);
                $data = ['status' => $job['status'] ?? $analysis->status, 'progress' => (float) ($job['progress'] ?? $analysis->progress)];
                if (($job['status'] ?? null) === 'done') {
                    $summary = $this->engine->analysisSummary($analysis->result_dir);
                    $data += ['progress' => 1.0, 'summary' => $summary, 'engine_version' => $summary['engine_version'] ?? $analysis->engine_version];
                    ActivityLog::record($analysis->project_id, 'analysis.completed', $analysis, [
                        'name' => $analysis->name,
                        'f0' => $summary['peaks']['selected']['frequency'] ?? null,
                        'status' => $summary['peaks']['status'] ?? null,
                    ]);
                } elseif (($job['status'] ?? null) === 'failed') {
                    $data['error'] = $job['error'] ?? 'Analysis failed.';
                    ActivityLog::record($analysis->project_id, 'analysis.failed', $analysis, ['error' => $data['error']]);
                }
                $analysis->update($data);
            } catch (EngineErrorException $e) {
                if ($e->status === 404) {
                    $analysis->update(['status' => 'failed', 'error' => 'Engine job no longer exists (engine restarted?).']);
                }
            }
        }

        if ($analysis->report_status && in_array($analysis->report_status, ['queued', 'running'], true) && $analysis->report_job_id) {
            try {
                $job = $this->engine->job($analysis->report_job_id);
                $status = $job['status'] ?? $analysis->report_status;
                $update = ['report_status' => $status];
                if ($status === 'done') {
                    $update['report_path'] = $job['result']['output_path'] ?? $analysis->report_path;
                    ActivityLog::record($analysis->project_id, 'report.generated', $analysis);
                }
                $analysis->update($update);
            } catch (EngineErrorException $e) {
                if ($e->status === 404) {
                    $analysis->update(['report_status' => 'failed']);
                }
            }
        }

        return $analysis;
    }
}
