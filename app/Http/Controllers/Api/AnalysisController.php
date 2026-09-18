<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreAnalysisRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Models\Recording;
use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\EngineErrorException;
use App\Services\Engine\JobSync;
use App\Services\Projects\AnalysisService;
use App\Services\Projects\ProjectStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class AnalysisController extends Controller
{
    private const EXPORTS = [
        'hvsr-csv' => 'hvsr_mean.csv',
        'windows-csv' => 'hvsr_windows.csv',
        'spectra-csv' => 'component_spectra.csv',
        'summary-csv' => 'summary.csv',
        'summary-json' => 'summary.json',
        'config-json' => 'config.json',
        'azimuthal-csv' => 'azimuthal.csv',
        'geopsy-hv' => 'hvsr_mean.hv',
    ];

    private const FIGURES = ['hvsr', 'spectra', 'windows', 'azimuthal', 'peak_distribution'];

    public function __construct(
        private readonly EngineClientInterface $engine,
        private readonly AnalysisService $analyses,
        private readonly JobSync $sync,
        private readonly ProjectStorage $storage,
    ) {}

    public function store(StoreAnalysisRequest $request, Recording $recording): JsonResponse
    {
        $analysis = $this->analyses->create($recording, $request->validated());

        return response()->json(Json::analysis($analysis, null, $this->initialJob($analysis)), 201);
    }

    public function show(Request $request, Analysis $analysis): JsonResponse
    {
        $analysis = $this->sync->syncAnalysis($analysis);
        $include = $request->query('include', 'result');
        $result = null;
        if ($analysis->status === 'done' && $include === 'result') {
            try {
                $result = $this->engine->analysisLoad($analysis->result_dir);
            } catch (EngineErrorException $e) {
                $result = null;
            }
        }
        $job = $analysis->isActive() && $analysis->job_id ? $this->safeJob($analysis->job_id) : null;

        return response()->json(Json::analysis($analysis, $result, $job));
    }

    public function update(Request $request, Analysis $analysis): JsonResponse
    {
        $data = $request->validate(['name' => ['required', 'string', 'max:160']]);
        $analysis->update($data);

        return response()->json(Json::analysis($analysis));
    }

    public function destroy(Analysis $analysis): JsonResponse
    {
        if ($analysis->isActive() && $analysis->job_id) {
            try {
                $this->engine->cancelJob($analysis->job_id);
            } catch (\Throwable) {
            }
        }
        if ($analysis->result_dir && is_dir($analysis->result_dir)) {
            File::deleteDirectory($analysis->result_dir);
        }
        ActivityLog::record($analysis->project_id, 'analysis.deleted', $analysis, ['name' => $analysis->name]);
        $analysis->delete();

        return response()->json(['deleted' => true]);
    }

    public function cancel(Analysis $analysis): JsonResponse
    {
        if ($analysis->isActive() && $analysis->job_id) {
            $this->engine->cancelJob($analysis->job_id);
            $analysis->update(['status' => 'cancelled']);
            ActivityLog::record($analysis->project_id, 'analysis.cancelled', $analysis);
        }

        return response()->json(Json::analysis($analysis));
    }

    public function windowCurves(Analysis $analysis): JsonResponse
    {
        $this->assertDone($analysis);

        return response()->json($this->engine->windowCurves($analysis->result_dir));
    }

    public function rerun(Analysis $analysis): JsonResponse
    {
        $analysis = $this->analyses->rerun($analysis);

        return response()->json(Json::analysis($analysis, null, $this->initialJob($analysis)));
    }

    public function selectPeak(Request $request, Analysis $analysis): JsonResponse
    {
        $data = $request->validate(['frequency' => ['present', 'nullable', 'numeric', 'gt:0']]);
        $result = $this->analyses->selectPeak($analysis, $data['frequency'] === null ? null : (float) $data['frequency']);

        return response()->json(Json::analysis($analysis->fresh(), $result));
    }

    public function export(Analysis $analysis, string $kind): BinaryFileResponse|JsonResponse
    {
        $this->assertDone($analysis);
        if ($kind === 'windows-json') {
            return response()->json($this->windowSet($analysis));
        }
        if (! isset(self::EXPORTS[$kind])) {
            return response()->json(['message' => 'Unknown export kind. Valid: '.implode(', ', array_keys(self::EXPORTS))], 404);
        }
        $file = $this->storage->safe($analysis->result_dir.'/exports/'.self::EXPORTS[$kind]);
        if (! is_file($file)) {
            return response()->json(['message' => 'Export file is not available for this analysis ('.self::EXPORTS[$kind].').'], 404);
        }

        return response()->download($file, $this->downloadName($analysis, self::EXPORTS[$kind]));
    }

    public function figure(Request $request, Analysis $analysis): BinaryFileResponse|JsonResponse
    {
        $q = $request->validate([
            'figure' => ['required', 'in:'.implode(',', self::FIGURES)],
            'format' => ['required', 'in:png,svg,pdf'],
            'theme' => ['nullable', 'in:light,dark'],
        ]);
        $this->assertDone($analysis);
        $out = $this->storage->safe($analysis->result_dir.'/exports/'.$q['figure'].'.'.$q['format']);
        $this->engine->exportFigure([
            'analysis_dir' => $analysis->result_dir,
            'figure' => $q['figure'],
            'format' => $q['format'],
            'output_path' => $out,
            'theme' => $q['theme'] ?? 'light',
        ]);
        if (! is_file($out)) {
            return response()->json(['message' => 'The engine did not produce the figure file.'], 500);
        }

        return response()->download($out, $this->downloadName($analysis, $q['figure'].'.'.$q['format']));
    }

    public function createReport(Analysis $analysis): JsonResponse
    {
        $this->assertDone($analysis);
        if (in_array($analysis->report_status, ['queued', 'running'], true)) {
            return response()->json(['message' => 'A report is already being generated.', 'report_status' => $analysis->report_status], 409);
        }
        $out = $this->storage->safe($analysis->result_dir.'/report.pdf');
        $job = $this->engine->exportReport([
            'analysis_dir' => $analysis->result_dir,
            'output_path' => $out,
            'context' => $this->analyses->reportContext($analysis),
        ]);
        $analysis->update(['report_job_id' => $job['id'] ?? null, 'report_status' => $job['status'] ?? 'queued', 'report_path' => $out]);
        ActivityLog::record($analysis->project_id, 'report.requested', $analysis);

        return response()->json(['job' => $job, 'analysis' => Json::analysis($analysis)], 202);
    }

    public function report(Analysis $analysis): BinaryFileResponse|JsonResponse
    {
        $analysis = $this->sync->syncAnalysis($analysis);
        if (in_array($analysis->report_status, ['queued', 'running'], true)) {
            return response()->json(['message' => 'Report is still being generated.', 'report_status' => $analysis->report_status], 409);
        }
        if ($analysis->report_status !== 'done' || ! $analysis->report_path || ! is_file($analysis->report_path)) {
            return response()->json(['message' => 'No report has been generated for this analysis yet.', 'report_status' => $analysis->report_status], 404);
        }

        return response()->download($analysis->report_path, $this->downloadName($analysis, 'report.pdf'));
    }

    public function updateModels(Request $request, Analysis $analysis): JsonResponse
    {
        $data = $request->validate([
            'models' => ['present', 'array', 'max:50'],
            'models.*.id' => ['nullable', 'string', 'max:40'],
            'models.*.name' => ['required', 'string', 'max:120'],
            'models.*.layers' => ['required', 'array', 'min:1', 'max:50'],
            'models.*.layers.*.thickness_m' => ['present', 'nullable', 'numeric', 'gt:0'],
            'models.*.layers.*.vs' => ['required', 'numeric', 'gt:0'],
            'models.*.layers.*.vp' => ['nullable', 'numeric', 'gt:0'],
            'models.*.layers.*.poisson' => ['nullable', 'numeric', 'gt:0', 'lt:0.5'],
            'models.*.layers.*.density' => ['nullable', 'numeric', 'gt:0'],
            'models.*.layers.*.qs' => ['nullable', 'numeric', 'gt:0'],
            'models.*.layers.*.qp' => ['nullable', 'numeric', 'gt:0'],
            'models.*.vs30_offset_m' => ['nullable', 'numeric', 'min:0'],
            'models.*.created_at' => ['nullable', 'string', 'max:40'],
        ]);
        $models = [];
        foreach (array_values($data['models']) as $m) {
            $models[] = [
                'id' => $m['id'] ?? (string) Str::ulid(),
                'name' => $m['name'],
                'layers' => array_values($m['layers']),
                'vs30_offset_m' => (float) ($m['vs30_offset_m'] ?? 0),
                'created_at' => $m['created_at'] ?? now()->toIso8601String(),
            ];
        }
        $analysis->update(['models' => $models]);
        ActivityLog::record($analysis->project_id, 'analysis.models_updated', $analysis, ['count' => count($models)]);

        return response()->json(['models' => $models]);
    }

    /** Window set export: {mode, params, windows[]} built from result.json. */
    private function windowSet(Analysis $analysis): array
    {
        $result = $this->engine->analysisLoad($analysis->result_dir);
        $params = $analysis->params ?? [];
        $windows = $result['windows'] ?? [];
        $items = array_map(fn ($w) => [
            'start_s' => $w['start_s'] ?? null,
            'end_s' => $w['end_s'] ?? null,
            'accepted' => (bool) ($w['accepted'] ?? false),
            'reason' => $w['reason'] ?? null,
        ], $windows['items'] ?? []);

        return [
            'format' => 'quakelogic-hvsr-studio-windows/1',
            'analysis' => $analysis->ulid,
            'recording' => $analysis->recording->ulid,
            'mode' => $windows['mode'] ?? ($params['windows']['mode'] ?? 'fixed'),
            'params' => $params['windows'] ?? ['length_s' => $windows['length_s'] ?? ($params['window_length_s'] ?? null), 'overlap' => $windows['overlap'] ?? ($params['overlap'] ?? null)],
            'windows' => $items,
        ];
    }

    private function assertDone(Analysis $analysis): void
    {
        $analysis = $this->sync->syncAnalysis($analysis);
        if ($analysis->status !== 'done' || ! $analysis->result_dir) {
            abort(response()->json(['message' => 'Analysis has not finished (status: '.$analysis->status.').'], 409));
        }
    }

    private function initialJob(Analysis $analysis): ?array
    {
        return $analysis->job_id ? ['id' => $analysis->job_id, 'status' => $analysis->status, 'progress' => $analysis->progress] : null;
    }

    private function safeJob(?string $jobId): ?array
    {
        if (! $jobId) {
            return null;
        }
        try {
            return $this->engine->job($jobId);
        } catch (\Throwable) {
            return null;
        }
    }

    private function downloadName(Analysis $analysis, string $file): string
    {
        $base = preg_replace('/[^A-Za-z0-9_-]+/', '_', $analysis->recording->name.'_'.$analysis->name) ?: 'analysis';

        return trim($base, '_').'_'.$file;
    }
}
