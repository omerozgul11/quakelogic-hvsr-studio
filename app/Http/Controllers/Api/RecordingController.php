<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreRecordingRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\ProcessingRun;
use App\Models\Project;
use App\Models\Recording;
use App\Models\Station;
use App\Services\Engine\EngineClientInterface;
use App\Services\Projects\ImportBlockedException;
use App\Services\Projects\RecordingImportService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;

class RecordingController extends Controller
{
    public function __construct(private readonly EngineClientInterface $engine) {}

    public function store(StoreRecordingRequest $request, Project $project, RecordingImportService $import): JsonResponse
    {
        try {
            $recording = $import->createRecording($project, $request->validated());
        } catch (ImportBlockedException $e) {
            return response()->json([
                'message' => 'The recording could not be imported. Fix the reported problems and try again.',
                'validation' => $e->validation,
            ], 422);
        }

        return response()->json(Json::recording($recording, true), 201);
    }

    public function show(Recording $recording): JsonResponse
    {
        $recording->load(['files', 'station']);

        return response()->json(Json::recording($recording, true));
    }

    public function update(Request $request, Recording $recording): JsonResponse
    {
        $data = $request->validate([
            'name' => ['sometimes', 'required', 'string', 'max:160'],
            'station_id' => ['nullable', 'string', 'size:26'],
            'notes' => ['nullable', 'string', 'max:5000'],
            'is_synthetic' => ['nullable', 'boolean'],
        ]);
        if (array_key_exists('station_id', $data)) {
            $station = $data['station_id'] ? Station::query()->where('project_id', $recording->project_id)->where('ulid', $data['station_id'])->first() : null;
            if ($data['station_id'] && ! $station) {
                throw ValidationException::withMessages(['station_id' => 'Unknown station.']);
            }
            $data['station_id'] = $station?->id;
        }
        $recording->update($data);
        ActivityLog::record($recording->project_id, 'recording.updated', $recording, $data);

        return response()->json(Json::recording($recording->fresh(['files', 'station']), true));
    }

    public function destroy(Recording $recording, RecordingImportService $import): JsonResponse
    {
        $import->delete($recording);

        return response()->json(['deleted' => true]);
    }

    public function data(Request $request, Recording $recording): JsonResponse
    {
        $q = $request->validate([
            'run' => ['nullable', 'string', 'size:26'],
            't_start' => ['nullable', 'numeric'],
            't_end' => ['nullable', 'numeric'],
            'max_points' => ['nullable', 'integer', 'min:100', 'max:200000'],
            'components' => ['nullable', 'string'],
        ]);

        $components = isset($q['components']) ? array_values(array_intersect(explode(',', $q['components']), ['n', 'e', 'z'])) : ['n', 'e', 'z'];

        return response()->json($this->engine->recordingData([
            'path' => $this->inputPath($recording, $q['run'] ?? null),
            't_start' => isset($q['t_start']) ? (float) $q['t_start'] : null,
            't_end' => isset($q['t_end']) ? (float) $q['t_end'] : null,
            'max_points' => (int) ($q['max_points'] ?? 4000),
            'components' => $components ?: ['n', 'e', 'z'],
        ]));
    }

    public function spectra(Request $request, Recording $recording): JsonResponse
    {
        $request->validate([
            'run_id' => ['nullable', 'string', 'size:26'],
            'kind' => ['required', 'in:fas,psd,spectrogram'],
        ]);

        $payload = $request->except(['run_id']);
        $payload['path'] = $this->inputPath($recording, $request->input('run_id'));

        return response()->json($this->engine->recordingSpectra($payload));
    }

    public function preview(Request $request, Recording $recording): JsonResponse
    {
        $request->validate([
            'steps' => ['required', 'array'],
            'steps.*.op' => ['required', 'string'],
            't_start' => ['nullable', 'numeric'],
            't_end' => ['nullable', 'numeric'],
            'max_points' => ['nullable', 'integer', 'min:100', 'max:200000'],
        ]);
        $this->assertReady($recording);

        return response()->json($this->engine->processingPreview([
            'input_path' => $recording->canonical_path,
            'steps' => array_values($request->input('steps')),
            't_start' => $request->input('t_start'),
            't_end' => $request->input('t_end'),
            'max_points' => (int) $request->input('max_points', 4000),
        ]));
    }

    public function windows(Request $request, Recording $recording): JsonResponse
    {
        $request->validate([
            'run_id' => ['nullable', 'string', 'size:26'],
            'params' => ['required', 'array'],
            'window_overrides' => ['nullable', 'array'],
        ]);

        return response()->json($this->engine->hvsrWindows([
            'input_path' => $this->inputPath($recording, $request->input('run_id')),
            'params' => $request->input('params'),
            'window_overrides' => (object) ($request->input('window_overrides') ?? []),
        ]));
    }

    public function samples(Request $request, Recording $recording): JsonResponse
    {
        $q = $request->validate([
            'component' => ['required', 'in:n,e,z'],
            'run' => ['nullable', 'string', 'size:26'],
            't_start' => ['nullable', 'numeric', 'min:0'],
            't_end' => ['nullable', 'numeric', 'min:0'],
        ]);
        $tStart = isset($q['t_start']) ? (float) $q['t_start'] : 0.0;
        $tEnd = isset($q['t_end']) ? (float) $q['t_end'] : null;
        $fs = (float) ($recording->sample_rate ?: 0);
        $span = $tEnd === null ? (float) ($recording->duration_s ?: 0) - $tStart : $tEnd - $tStart;
        $needed = (int) max(1, ceil($span * $fs) + 1);
        if ($needed > 4_000_000) {
            throw ValidationException::withMessages(['t_end' => 'At most 4,000,000 samples can be requested at once; narrow the time range.']);
        }

        $data = $this->engine->recordingData([
            'path' => $this->inputPath($recording, $q['run'] ?? null),
            't_start' => $tStart,
            't_end' => $tEnd,
            'max_points' => max($needed, (int) ($recording->n_samples ?: 0), 60000),
            'components' => [$q['component']],
        ]);
        if (! empty($data['downsampled']) && (int) ($data['n_display'] ?? 0) < (int) ($data['n_source'] ?? 0)) {
            throw ValidationException::withMessages(['t_end' => 'The engine returned a down-sampled envelope; the requested range is too long for full-resolution playback.']);
        }
        $comp = $data['components'][$q['component']] ?? ['v' => []];

        return response()->json([
            'fs' => (float) ($data['fs'] ?? $fs),
            't0' => (float) ($data['t_start'] ?? $tStart),
            'n' => count($comp['v'] ?? []),
            'values' => array_values($comp['v'] ?? []),
        ]);
    }

    public function importWindows(Request $request, Recording $recording): JsonResponse
    {
        $data = $request->validate([
            'mode' => ['nullable', 'string', 'in:fixed,auto_variable,custom'],
            'params' => ['nullable', 'array'],
            'windows' => ['required', 'array', 'min:1', 'max:20000'],
            'windows.*.start_s' => ['required', 'numeric', 'min:0'],
            'windows.*.end_s' => ['required', 'numeric', 'gt:0'],
            'windows.*.accepted' => ['nullable', 'boolean'],
            'windows.*.reason' => ['nullable', 'string', 'max:40'],
        ]);
        $duration = (float) ($recording->duration_s ?: PHP_FLOAT_MAX);
        $custom = [];
        $overrides = [];
        $skipped = 0;
        $i = 0;
        foreach ($data['windows'] as $w) {
            $start = (float) $w['start_s'];
            $end = (float) $w['end_s'];
            if ($end <= $start || $start >= $duration) {
                $skipped++;

                continue;
            }
            $custom[] = [round($start, 4), round(min($end, $duration), 4)];
            $accepted = (bool) ($w['accepted'] ?? true);
            if (! $accepted) {
                $overrides[(string) $i] = ['accepted' => false, 'reason' => 'manual'];
            }
            $i++;
        }
        if (! $custom) {
            throw ValidationException::withMessages(['windows' => 'No usable windows in the file.']);
        }

        return response()->json([
            'mode' => 'custom',
            'source_mode' => $data['mode'] ?? 'custom',
            'params' => $data['params'] ?? null,
            'custom' => $custom,
            'window_overrides' => (object) $overrides,
            'counts' => ['imported' => count($custom), 'rejected' => count($overrides), 'skipped' => $skipped],
        ]);
    }

    private function inputPath(Recording $recording, ?string $runUlid): string
    {
        $this->assertReady($recording);
        if ($runUlid) {
            $run = ProcessingRun::query()->where('recording_id', $recording->id)->where('ulid', $runUlid)->first();
            if (! $run) {
                throw ValidationException::withMessages(['run' => 'Unknown processing run for this recording.']);
            }
            if ($run->status !== 'done' || ! $run->output_path) {
                throw ValidationException::withMessages(['run' => 'Processing run has not finished.']);
            }

            return $run->output_path;
        }

        return $recording->canonical_path;
    }

    private function assertReady(Recording $recording): void
    {
        if ($recording->status !== 'ready' || ! $recording->canonical_path) {
            throw ValidationException::withMessages(['recording' => 'Recording is not ready.']);
        }
    }
}
