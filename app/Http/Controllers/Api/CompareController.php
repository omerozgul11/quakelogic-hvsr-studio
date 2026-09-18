<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Analysis;
use App\Models\Project;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CompareController extends Controller
{
    public function compare(Request $request, Project $project, EngineClientInterface $engine): JsonResponse
    {
        $data = $request->validate([
            'analysis_ids' => ['required', 'array', 'min:1', 'max:24'],
            'analysis_ids.*' => ['string', 'size:26'],
        ]);

        $analyses = Analysis::query()->where('project_id', $project->id)->whereIn('ulid', $data['analysis_ids'])
            ->with(['recording.station', 'run'])->get()->keyBy('ulid');

        $out = [];
        foreach ($data['analysis_ids'] as $ulid) {
            $a = $analyses[$ulid] ?? null;
            if (! $a) {
                $out[] = ['analysis_id' => $ulid, 'error' => 'Unknown analysis'];

                continue;
            }
            if ($a->status !== 'done') {
                $out[] = ['analysis_id' => $ulid, 'name' => $a->name, 'error' => 'Analysis not finished ('.$a->status.')'];

                continue;
            }
            try {
                $result = $engine->analysisLoad($a->result_dir);
            } catch (\Throwable $e) {
                $out[] = ['analysis_id' => $ulid, 'name' => $a->name, 'error' => 'Result could not be loaded: '.$e->getMessage()];

                continue;
            }
            $selected = $result['curves']['selected'] ?? 'geometric';
            $curve = $result['curves'][$selected] ?? [];
            $out[] = [
                'analysis_id' => $a->ulid,
                'name' => $a->name,
                'recording_id' => $a->recording->ulid,
                'recording_name' => $a->recording->name,
                'station_code' => $a->recording->station?->code,
                'run_name' => $a->run?->name,
                'mean_method' => $selected,
                'band' => $curve['band'] ?? null,
                'frequency' => $result['frequency'] ?? [],
                'curve' => $curve['values'] ?? [],
                'lower' => $curve['lower'] ?? [],
                'upper' => $curve['upper'] ?? [],
                'peak' => $result['peaks']['selected'] ?? null,
                'peak_status' => $result['peaks']['status'] ?? null,
                'windows' => ['accepted' => $result['windows']['count_accepted'] ?? null, 'total' => $result['windows']['count_total'] ?? null],
                'sesame' => isset($result['sesame']) ? [
                    'reliability_passed' => $result['sesame']['reliability_passed'] ?? null,
                    'clarity_passed_count' => $result['sesame']['clarity_passed_count'] ?? null,
                    'clarity_passed' => $result['sesame']['clarity_passed'] ?? null,
                ] : null,
                'quality_flags' => $result['quality_flags'] ?? [],
                'params' => ['window_length_s' => $result['params']['window_length_s'] ?? null, 'smoothing' => $result['params']['smoothing'] ?? null, 'horizontal_method' => $result['params']['horizontal_method'] ?? null],
            ];
        }

        return response()->json($out);
    }
}
