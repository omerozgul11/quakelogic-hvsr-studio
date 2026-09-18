<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StorePresetRequest;
use App\Http\Requests\UpdatePresetRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\ProcessingPreset;
use App\Models\Project;
use Illuminate\Http\JsonResponse;

class PresetController extends Controller
{
    public function index(Project $project): JsonResponse
    {
        $presets = ProcessingPreset::query()
            ->where(fn ($q) => $q->whereNull('project_id')->orWhere('project_id', $project->id))
            ->orderByRaw('project_id IS NULL DESC')->orderBy('name')->get();

        return response()->json($presets->map(fn ($p) => Json::preset($p))->values());
    }

    public function store(StorePresetRequest $request, Project $project): JsonResponse
    {
        $data = $request->validated();
        $preset = $project->presets()->create([
            'name' => $data['name'],
            'description' => $data['description'] ?? null,
            'steps' => array_values($data['steps'] ?? []),
            'hvsr_params' => $data['hvsr_params'] ?? [],
        ]);
        ActivityLog::record($project->id, 'preset.created', $preset, ['name' => $preset->name]);

        return response()->json(Json::preset($preset), 201);
    }

    public function update(UpdatePresetRequest $request, ProcessingPreset $preset): JsonResponse
    {
        if ($preset->project_id === null) {
            return response()->json(['message' => 'Built-in presets cannot be edited. Duplicate it into the project first.'], 409);
        }
        $data = $request->validated();
        if (isset($data['steps'])) {
            $data['steps'] = array_values($data['steps']);
        }
        $preset->update($data);
        ActivityLog::record($preset->project_id, 'preset.updated', $preset, ['name' => $preset->name]);

        return response()->json(Json::preset($preset));
    }

    public function destroy(ProcessingPreset $preset): JsonResponse
    {
        if ($preset->project_id === null) {
            return response()->json(['message' => 'Built-in presets cannot be deleted.'], 409);
        }
        ActivityLog::record($preset->project_id, 'preset.deleted', $preset, ['name' => $preset->name]);
        $preset->delete();

        return response()->json(['deleted' => true]);
    }
}
