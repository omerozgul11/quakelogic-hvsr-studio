<?php

namespace App\Services\Engine;

/**
 * One method per Python service endpoint (see docs/architecture.md, "Python service API").
 * Every method returns the decoded JSON body of the engine response.
 */
interface EngineClientInterface
{
    public function health(): array;

    public function inspectFile(string $path): array;

    public function importRecording(array $request): array;

    public function recordingData(array $request): array;

    public function recordingSpectra(array $request): array;

    public function processingPreview(array $request): array;

    public function processingRun(array $request): array;

    public function filterResponse(array $request): array;

    public function hvsrWindows(array $request): array;

    public function hvsrAnalyze(array $request): array;

    public function selectPeak(string $analysisDir, ?float $frequency): array;

    public function analysisLoad(string $dir): array;

    public function analysisSummary(string $dir): array;

    public function windowCurves(string $dir): array;

    public function exportFigure(array $request): array;

    public function exportReport(array $request): array;

    public function job(string $jobId): array;

    public function cancelJob(string $jobId): array;

    public function modelHvsr(array $request): array;

    public function importCurve(string $path): array;
}
