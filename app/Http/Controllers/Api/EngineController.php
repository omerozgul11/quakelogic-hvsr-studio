<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;

class EngineController extends Controller
{
    public function filterResponse(Request $request, EngineClientInterface $engine): JsonResponse
    {
        $request->validate([
            'fs' => ['required', 'numeric', 'gt:0'],
            'step' => ['required', 'array'],
            'step.op' => ['required', 'in:filter,notch'],
            'n_points' => ['nullable', 'integer', 'min:64', 'max:65536'],
        ]);

        return response()->json($engine->filterResponse([
            'fs' => (float) $request->input('fs'),
            'step' => $request->input('step'),
            'n_points' => (int) $request->input('n_points', 1024),
        ]));
    }

    public function modelHvsr(Request $request, EngineClientInterface $engine): JsonResponse
    {
        $data = $request->validate([
            'layers' => ['required', 'array', 'min:1', 'max:50'],
            'layers.*.thickness_m' => ['present', 'nullable', 'numeric', 'gt:0'],
            'layers.*.vs' => ['required', 'numeric', 'gt:0'],
            'layers.*.vp' => ['nullable', 'numeric', 'gt:0'],
            'layers.*.poisson' => ['nullable', 'numeric', 'gt:0', 'lt:0.5'],
            'layers.*.density' => ['nullable', 'numeric', 'gt:0'],
            'layers.*.qs' => ['nullable', 'numeric', 'gt:0'],
            'layers.*.qp' => ['nullable', 'numeric', 'gt:0'],
            'freq_min' => ['nullable', 'numeric', 'gt:0'],
            'freq_max' => ['nullable', 'numeric', 'gt:0'],
            'n_freq' => ['nullable', 'integer', 'min:10', 'max:2000'],
            'vs30_offset_m' => ['nullable', 'numeric', 'min:0'],
        ]);
        $layers = array_values($data['layers']);
        $last = end($layers);
        if (($last['thickness_m'] ?? null) !== null) {
            throw ValidationException::withMessages(['layers' => 'The last layer is the half-space and must have no thickness (null).']);
        }
        foreach (array_slice($layers, 0, -1) as $i => $layer) {
            if (($layer['thickness_m'] ?? null) === null) {
                throw ValidationException::withMessages(['layers.'.$i.'.thickness_m' => 'Only the last layer (half-space) may have no thickness.']);
            }
            if (($layer['vp'] ?? null) === null && ($layer['poisson'] ?? null) === null) {
                throw ValidationException::withMessages(['layers.'.$i.'.vp' => 'Give either Vp or a Poisson ratio for every layer.']);
            }
        }
        if (($last['vp'] ?? null) === null && ($last['poisson'] ?? null) === null) {
            throw ValidationException::withMessages(['layers.'.(count($layers) - 1).'.vp' => 'Give either Vp or a Poisson ratio for the half-space.']);
        }
        if (isset($data['freq_min'], $data['freq_max']) && $data['freq_min'] >= $data['freq_max']) {
            throw ValidationException::withMessages(['freq_max' => 'freq_max must be greater than freq_min.']);
        }

        return response()->json($engine->modelHvsr([
            'layers' => $layers,
            'freq_min' => (float) ($data['freq_min'] ?? 0.2),
            'freq_max' => (float) ($data['freq_max'] ?? 100),
            'n_freq' => (int) ($data['n_freq'] ?? 200),
            'vs30_offset_m' => (float) ($data['vs30_offset_m'] ?? 0),
        ]));
    }

    public function job(string $job, EngineClientInterface $engine): JsonResponse
    {
        return response()->json($engine->job($job));
    }

    public function cancelJob(string $job, EngineClientInterface $engine): JsonResponse
    {
        return response()->json($engine->cancelJob($job));
    }
}
