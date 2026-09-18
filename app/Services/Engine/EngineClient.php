<?php

namespace App\Services\Engine;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Facades\Http;

class EngineClient implements EngineClientInterface
{
    public function __construct(
        private readonly string $baseUrl,
        private readonly ?string $token,
        private readonly int $timeout = 15,
        private readonly int $computeTimeout = 120,
    ) {}

    public static function fromConfig(): self
    {
        return new self(
            (string) config('hvsr.engine_url'),
            config('hvsr.engine_token'),
            (int) config('hvsr.engine_timeout', 15),
            (int) config('hvsr.engine_compute_timeout', 120),
        );
    }

    public function health(): array
    {
        return $this->get('/health', 5);
    }

    public function inspectFile(string $path): array
    {
        return $this->post('/files/inspect', ['path' => $path], $this->computeTimeout);
    }

    public function importRecording(array $request): array
    {
        return $this->post('/recordings/import', $request, max($this->computeTimeout, 300));
    }

    public function recordingData(array $request): array
    {
        return $this->post('/recordings/data', $request, $this->computeTimeout);
    }

    public function recordingSpectra(array $request): array
    {
        return $this->post('/recordings/spectra', $request, $this->computeTimeout);
    }

    public function processingPreview(array $request): array
    {
        return $this->post('/processing/preview', $request, $this->computeTimeout);
    }

    public function processingRun(array $request): array
    {
        return $this->post('/processing/run', $request);
    }

    public function filterResponse(array $request): array
    {
        return $this->post('/processing/filter-response', $request);
    }

    public function hvsrWindows(array $request): array
    {
        return $this->post('/hvsr/windows', $request, $this->computeTimeout);
    }

    public function hvsrAnalyze(array $request): array
    {
        return $this->post('/hvsr/analyze', $request);
    }

    public function selectPeak(string $analysisDir, ?float $frequency): array
    {
        return $this->post('/hvsr/select-peak', ['analysis_dir' => $analysisDir, 'frequency' => $frequency], $this->computeTimeout);
    }

    public function analysisLoad(string $dir): array
    {
        return $this->post('/analyses/load', ['dir' => $dir], $this->computeTimeout);
    }

    public function analysisSummary(string $dir): array
    {
        return $this->post('/analyses/summary', ['dir' => $dir]);
    }

    public function windowCurves(string $dir): array
    {
        return $this->post('/analyses/window-curves', ['dir' => $dir], $this->computeTimeout);
    }

    public function exportFigure(array $request): array
    {
        return $this->post('/exports/figure', $request, $this->computeTimeout);
    }

    public function exportReport(array $request): array
    {
        return $this->post('/exports/report', $request);
    }

    public function job(string $jobId): array
    {
        return $this->get('/jobs/'.rawurlencode($jobId));
    }

    public function cancelJob(string $jobId): array
    {
        return $this->post('/jobs/'.rawurlencode($jobId).'/cancel', []);
    }

    public function modelHvsr(array $request): array
    {
        return $this->post('/model/hvsr', $request, $this->computeTimeout);
    }

    public function importCurve(string $path): array
    {
        return $this->post('/curves/import', ['path' => $path], $this->computeTimeout);
    }

    private function request(int $timeout): PendingRequest
    {
        $req = Http::baseUrl($this->baseUrl)
            ->acceptJson()
            ->timeout($timeout)
            ->connectTimeout(3);

        if ($this->token) {
            $req = $req->withHeaders(['X-Engine-Token' => $this->token]);
        }

        return $req;
    }

    private function get(string $path, ?int $timeout = null): array
    {
        try {
            return $this->handle($this->request($timeout ?? $this->timeout)->get($path));
        } catch (ConnectionException $e) {
            throw new EngineUnavailableException($this->hint($e));
        }
    }

    private function post(string $path, array $body, ?int $timeout = null): array
    {
        try {
            return $this->handle($this->request($timeout ?? $this->timeout)->post($path, $body));
        } catch (ConnectionException $e) {
            throw new EngineUnavailableException($this->hint($e));
        }
    }

    private function handle(Response $response): array
    {
        $json = $response->json();

        if ($response->successful()) {
            return is_array($json) ? $json : [];
        }

        $error = is_array($json) ? ($json['error'] ?? null) : null;

        throw new EngineErrorException(
            $response->status(),
            (string) ($error['code'] ?? 'engine_error'),
            (string) ($error['message'] ?? ('Engine request failed with HTTP '.$response->status())),
            (array) ($error['details'] ?? []),
        );
    }

    private function hint(ConnectionException $e): string
    {
        return 'Could not reach the processing engine at '.$this->baseUrl.' ('.$e->getMessage().'). Start the application through the launcher, or run `python -m hvsr_service` from the engine directory.';
    }
}
