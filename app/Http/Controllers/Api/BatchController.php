<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreBatchRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\Batch;
use App\Models\ProcessingPreset;
use App\Models\Project;
use App\Models\Recording;
use App\Services\Batches\BatchAdvancer;
use Illuminate\Http\JsonResponse;
use Illuminate\Validation\ValidationException;

class BatchController extends Controller
{
    public function __construct(private readonly BatchAdvancer $advancer) {}

    public function store(StoreBatchRequest $request, Project $project): JsonResponse
    {
        $data = $request->validated();

        $preset = null;
        if (! empty($data['preset_id'])) {
            $preset = ProcessingPreset::query()->where('ulid', $data['preset_id'])
                ->where(fn ($q) => $q->whereNull('project_id')->orWhere('project_id', $project->id))->first();
            if (! $preset) {
                throw ValidationException::withMessages(['preset_id' => 'Unknown preset.']);
            }
        }

        $recordings = Recording::query()->where('project_id', $project->id)->whereIn('ulid', $data['recording_ids'])->get()->keyBy('ulid');
        $missing = array_diff($data['recording_ids'], $recordings->keys()->all());
        if ($missing) {
            throw ValidationException::withMessages(['recording_ids' => 'Unknown recordings: '.implode(', ', $missing)]);
        }

        $batch = $project->batches()->create([
            'name' => $data['name'],
            'preset_id' => $preset?->id,
            'run_steps' => (bool) ($data['run_steps'] ?? true),
            'status' => 'queued',
        ]);
        foreach (array_values(array_unique($data['recording_ids'])) as $i => $ulid) {
            $batch->items()->create(['recording_id' => $recordings[$ulid]->id, 'position' => $i, 'status' => 'queued']);
        }
        ActivityLog::record($project->id, 'batch.created', $batch, ['name' => $batch->name, 'items' => count($data['recording_ids']), 'preset' => $preset?->name]);

        $batch = $this->advancer->advance($batch->fresh(['items']));

        return response()->json(Json::batch($batch), 201);
    }

    public function show(Batch $batch): JsonResponse
    {
        $batch = $this->advancer->advance($batch);

        return response()->json(Json::batch($batch));
    }

    public function cancel(Batch $batch): JsonResponse
    {
        return response()->json(Json::batch($this->advancer->cancel($batch)));
    }

    public function destroy(Batch $batch): JsonResponse
    {
        if (in_array($batch->status, ['queued', 'running'], true)) {
            $this->advancer->cancel($batch);
        }
        $batch->delete();

        return response()->json(['deleted' => true]);
    }
}
