<?php

namespace App\Services\Batches;

use App\Models\ActivityLog;
use App\Models\Batch;
use App\Models\BatchItem;
use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\JobSync;
use App\Services\Projects\AnalysisService;
use App\Services\Projects\RunService;
use Throwable;

/**
 * Drives a batch forward. Called on every poll of GET /batches/{b} and right after creation.
 * Items are executed strictly one at a time: (optional) processing run, then the HVSR analysis.
 * A failing item is recorded and skipped; it never stops the remaining items.
 */
class BatchAdvancer
{
    public function __construct(
        private readonly EngineClientInterface $engine,
        private readonly JobSync $sync,
        private readonly RunService $runs,
        private readonly AnalysisService $analyses,
    ) {}

    public function advance(Batch $batch): Batch
    {
        if (in_array($batch->status, ['done', 'cancelled'], true)) {
            return $batch;
        }
        $batch->status = 'running';
        $batch->save();

        // Guard against runaway loops: at most one submission per item per call.
        $guard = 0;
        while ($guard++ < 50) {
            $item = $batch->items()->whereIn('status', ['queued', 'running'])->orderBy('position')->first();
            if (! $item) {
                $batch->update(['status' => 'done']);
                ActivityLog::record($batch->project_id, 'batch.completed', $batch, ['name' => $batch->name]);
                break;
            }
            $batch->update(['current_index' => $item->position]);

            if ($item->status === 'queued') {
                $this->start($batch, $item);
                if ($item->status === 'failed') {
                    continue;
                }
            }

            $state = $this->progress($batch, $item);
            if ($state === 'waiting') {
                break;
            }
        }

        return $batch->fresh(['items']);
    }

    public function cancel(Batch $batch): Batch
    {
        foreach ($batch->items()->whereIn('status', ['queued', 'running'])->get() as $item) {
            if ($item->status === 'running') {
                $this->cancelItemJob($item);
            }
            $item->update(['status' => 'cancelled']);
        }
        $batch->update(['status' => 'cancelled']);
        ActivityLog::record($batch->project_id, 'batch.cancelled', $batch);

        return $batch->fresh(['items']);
    }

    private function start(Batch $batch, BatchItem $item): void
    {
        $preset = $batch->preset;
        $recording = $item->recording;
        $item->status = 'running';
        $item->save();

        try {
            if ($batch->run_steps && $preset && ! empty($preset->steps)) {
                $run = $this->runs->create($recording, $batch->name.' — '.$preset->name, $preset->steps);
                $item->update(['processing_run_id' => $run->id]);
            } else {
                $this->submitAnalysis($batch, $item, null);
            }
        } catch (Throwable $e) {
            $this->fail($item, $e->getMessage());
        }
    }

    /** @return 'waiting'|'advanced' */
    private function progress(Batch $batch, BatchItem $item): string
    {
        try {
            if ($item->processing_run_id && ! $item->analysis_id) {
                $run = $this->sync->syncRun($item->run);
                if ($run->isActive()) {
                    return 'waiting';
                }
                if ($run->status !== 'done') {
                    $this->fail($item, $run->error ?: 'Processing run '.$run->status.'.');

                    return 'advanced';
                }
                $this->submitAnalysis($batch, $item, $run->ulid);
            }

            if ($item->analysis_id) {
                $analysis = $this->sync->syncAnalysis($item->analysis);
                if ($analysis->isActive()) {
                    return 'waiting';
                }
                if ($analysis->status === 'done') {
                    $item->update(['status' => 'done']);
                } else {
                    $this->fail($item, $analysis->error ?: 'Analysis '.$analysis->status.'.');
                }
            }
        } catch (Throwable $e) {
            $this->fail($item, $e->getMessage());
        }

        return 'advanced';
    }

    private function submitAnalysis(Batch $batch, BatchItem $item, ?string $runUlid): void
    {
        $preset = $batch->preset;
        $analysis = $this->analyses->create($item->recording, [
            'name' => $batch->name.' — '.$item->recording->name,
            'run_id' => $runUlid,
            'params' => $preset?->hvsr_params ?? [],
            'window_overrides' => [],
            'manual_peak' => null,
        ]);
        $item->update(['analysis_id' => $analysis->id]);
    }

    private function fail(BatchItem $item, string $error): void
    {
        $item->update(['status' => 'failed', 'error' => $error]);
        ActivityLog::record($item->batch->project_id, 'batch.item_failed', $item->batch, ['recording' => $item->recording?->ulid, 'error' => $error]);
    }

    private function cancelItemJob(BatchItem $item): void
    {
        $jobId = $item->analysis?->job_id ?: $item->run?->job_id;
        if ($jobId) {
            try {
                $this->engine->cancelJob($jobId);
            } catch (Throwable) {
            }
        }
        $item->analysis?->update(['status' => 'cancelled']);
        if ($item->run && $item->run->isActive()) {
            $item->run->update(['status' => 'cancelled']);
        }
    }
}
