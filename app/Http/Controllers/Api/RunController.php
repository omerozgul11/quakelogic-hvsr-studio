<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreRunRequest;
use App\Http\Serializers\Json;
use App\Models\ProcessingRun;
use App\Models\Recording;
use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\JobSync;
use App\Services\Projects\RunService;
use Illuminate\Http\JsonResponse;

class RunController extends Controller
{
    public function store(StoreRunRequest $request, Recording $recording, RunService $runs, EngineClientInterface $engine): JsonResponse
    {
        $data = $request->validated();
        $run = $runs->create($recording, $data['name'] ?? ('Processing '.now()->format('Y-m-d H:i')), $data['steps']);
        $job = $run->job_id ? ['id' => $run->job_id, 'status' => $run->status, 'progress' => $run->progress] : null;

        return response()->json(['run' => Json::run($run, $job), 'job' => $job], 201);
    }

    public function show(ProcessingRun $run, JobSync $sync, EngineClientInterface $engine): JsonResponse
    {
        $run = $sync->syncRun($run);
        $job = $run->isActive() && $run->job_id ? $this->safeJob($engine, $run->job_id) : null;

        return response()->json(Json::run($run, $job));
    }

    public function destroy(ProcessingRun $run, RunService $runs): JsonResponse
    {
        $runs->delete($run);

        return response()->json(['deleted' => true]);
    }

    private function safeJob(EngineClientInterface $engine, string $jobId): ?array
    {
        try {
            return $engine->job($jobId);
        } catch (\Throwable) {
            return null;
        }
    }
}
