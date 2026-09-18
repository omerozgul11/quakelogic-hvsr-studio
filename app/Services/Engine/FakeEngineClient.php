<?php

namespace App\Services\Engine;

use Illuminate\Support\Str;

/**
 * Deterministic stand-in for the Python service used by the PHP test-suite.
 * Produces contract-shaped responses and writes fake result files on disk.
 */
class FakeEngineClient implements EngineClientInterface
{
    /** @var array<string, array> */
    public array $jobs = [];

    /** @var array<string, array> */
    public array $calls = [];

    /** If set, importRecording returns a blocking validation failure. */
    public bool $importBlocking = false;

    /** Job ids that should fail when polled. */
    public array $failJobs = [];

    /** When true jobs complete on the first poll; otherwise they need `pollsToFinish` polls. */
    public int $pollsToFinish = 1;

    public bool $down = false;

    private int $jobCounter = 0;

    public function health(): array
    {
        $this->guard();

        return [
            'status' => 'ok', 'engine_version' => '1.0.0-fake', 'service_version' => '1.0.0-fake', 'python' => '3.12',
            'versions' => ['numpy' => 'x', 'scipy' => 'x', 'obspy' => 'x', 'pandas' => 'x', 'matplotlib' => 'x'],
            'workers' => 1, 'jobs_running' => 0,
        ];
    }

    public function inspectFile(string $path): array
    {
        $this->log(__FUNCTION__, compact('path'));
        $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
        $mseed = in_array($ext, ['mseed', 'gse', 'seg', 'sg2', 'sac', 'msd', 'miniseed'], true);
        $format = $ext === 'saf' ? 'saf' : ($ext === 'mseed' ? 'mseed' : ($mseed ? 'seismic' : 'ascii'));

        return [
            'path' => $path,
            'size_bytes' => is_file($path) ? filesize($path) : 0,
            'sha256' => is_file($path) ? hash_file('sha256', $path) : str_repeat('0', 64),
            'format' => $format,
            'saf' => $format === 'saf' ? ['sample_rate' => 100.0, 'n_samples' => 60000, 'start_time' => '2025-01-01T00:00:00.000000Z', 'channels' => ['V', 'N', 'E']] : null,
            'ascii' => ($mseed || $format === 'saf') ? null : [
                'encoding' => 'utf-8', 'delimiter' => ',', 'decimal' => '.', 'header_rows' => 1, 'comment_prefix' => '#',
                'columns' => [
                    ['index' => 0, 'name' => 't', 'numeric' => true, 'sample' => [0, 0.01]],
                    ['index' => 1, 'name' => 'N', 'numeric' => true, 'sample' => [1.0, 2.0]],
                    ['index' => 2, 'name' => 'E', 'numeric' => true, 'sample' => [1.0, 2.0]],
                    ['index' => 3, 'name' => 'Z', 'numeric' => true, 'sample' => [1.0, 2.0]],
                ],
                'n_rows_estimate' => 1000, 'preview_lines' => ['t,N,E,Z', '0,1,1,1'], 'preview_rows' => [[0, 1, 1, 1]],
                'time_column_guess' => ['index' => 0, 'kind' => 'seconds', 'sample_rate_estimate' => 100.0],
                'sample_rate_hint' => 100.0,
            ],
            'mseed' => $mseed ? ['traces' => [
                ['id' => 'XX.SYN..HHN', 'network' => 'XX', 'station' => 'SYN', 'location' => '', 'channel' => 'HHN', 'starttime' => '2025-01-01T00:00:00.000000Z', 'endtime' => '2025-01-01T00:10:00.000000Z', 'sampling_rate' => 100.0, 'npts' => 60000, 'segments' => 1, 'has_gaps' => false],
                ['id' => 'XX.SYN..HHE', 'network' => 'XX', 'station' => 'SYN', 'location' => '', 'channel' => 'HHE', 'starttime' => '2025-01-01T00:00:00.000000Z', 'endtime' => '2025-01-01T00:10:00.000000Z', 'sampling_rate' => 100.0, 'npts' => 60000, 'segments' => 1, 'has_gaps' => false],
                ['id' => 'XX.SYN..HHZ', 'network' => 'XX', 'station' => 'SYN', 'location' => '', 'channel' => 'HHZ', 'starttime' => '2025-01-01T00:00:00.000000Z', 'endtime' => '2025-01-01T00:10:00.000000Z', 'sampling_rate' => 100.0, 'npts' => 60000, 'segments' => 1, 'has_gaps' => false],
            ]] : null,
        ];
    }

    public function importRecording(array $request): array
    {
        $this->log(__FUNCTION__, $request);

        if ($this->importBlocking) {
            return [
                'ok' => false,
                'meta' => null,
                'validation' => ['blocking' => true, 'issues' => [
                    ['code' => 'nan_values', 'severity' => 'error', 'message' => 'Component Z contains 12 NaN samples.', 'details' => ['component' => 'z', 'count' => 12]],
                ]],
            ];
        }

        $meta = [
            'fs' => 100.0,
            'start_time' => '2025-01-01T00:00:00.000000Z',
            'n_samples' => 60000,
            'duration_s' => 600.0,
            'units' => $request['ascii']['units'] ?? 'counts',
            'unit_kind' => $request['ascii']['unit_kind'] ?? 'raw',
            'channels' => ['n' => 'HHN', 'e' => 'HHE', 'z' => 'HHZ'],
            'station' => $request['metadata']['station'] ?? 'SYN',
            'network' => $request['metadata']['network'] ?? 'XX',
            'location' => '',
            'orientation_deg' => $request['metadata']['orientation_deg'] ?? 0.0,
            'source_files' => array_map(fn ($s) => $s['path'], $request['sources'] ?? []),
            'import_settings' => $request,
            'is_synthetic' => (bool) ($request['metadata']['is_synthetic'] ?? false),
            'engine_version' => '1.0.0-fake',
        ];

        if (! empty($request['output_path'])) {
            @mkdir(dirname($request['output_path']), 0777, true);
            file_put_contents($request['output_path'], 'FAKE-NPZ');
        }

        return [
            'ok' => true,
            'meta' => $meta,
            'validation' => ['blocking' => false, 'issues' => [
                ['code' => 'unit_unknown', 'severity' => 'info', 'message' => 'Units were not verified.', 'details' => []],
            ]],
        ];
    }

    public function recordingData(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        $t = [0, 1, 2, 3];
        $comp = fn () => ['t' => $t, 'v' => [0.1, -0.1, 0.2, -0.2]];
        $full = (int) ($request['max_points'] ?? 0) >= 60000;
        $components = [];
        foreach (($request['components'] ?? ['n', 'e', 'z']) as $c) {
            $components[$c] = $full ? ['t' => [0, 0.01, 0.02, 0.03, 0.04], 'v' => [1, 2, 3, 4, 5]] : $comp();
        }

        return [
            'fs' => 100.0, 'start_time' => '2025-01-01T00:00:00.000000Z', 'duration_s' => 600.0, 'n_samples' => 60000,
            't_start' => $request['t_start'] ?? 0, 't_end' => $request['t_end'] ?? 600.0,
            'downsampled' => ! $full, 'n_display' => $full ? 60000 : 4, 'method' => $full ? 'full' : 'minmax',
            'components' => $components,
        ];
    }

    public function recordingSpectra(array $request): array
    {
        $this->log(__FUNCTION__, $request);

        return ['frequency' => [0.5, 1, 2], 'components' => ['n' => [1, 2, 1], 'e' => [1, 2, 1], 'z' => [1, 1, 1]], 'units' => 'counts*s', 'definition' => 'fake'];
    }

    public function processingPreview(array $request): array
    {
        $this->log(__FUNCTION__, $request);

        return [
            'raw' => $this->recordingData($request),
            'processed' => $this->recordingData($request),
            'warnings' => [['step_index' => 0, 'code' => 'edge_effects', 'message' => 'Filter transients near the record edges.']],
            'applied' => $request['steps'] ?? [],
            'fs_out' => 100.0,
        ];
    }

    public function processingRun(array $request): array
    {
        $this->log(__FUNCTION__, $request);

        return $this->createJob('processing_run', [
            'output_path' => $request['output_path'],
            'meta' => ['fs' => 100.0, 'n_samples' => 60000, 'duration_s' => 600.0, 'start_time' => '2025-01-01T00:00:00.000000Z', 'units' => 'counts'],
            'warnings' => [],
            'applied' => $request['steps'] ?? [],
        ], function () use ($request) {
            @mkdir(dirname($request['output_path']), 0777, true);
            file_put_contents($request['output_path'], 'FAKE-NPZ-PROCESSED');
        });
    }

    public function filterResponse(array $request): array
    {
        $this->log(__FUNCTION__, $request);

        return ['frequency' => [0.1, 1, 10], 'magnitude_db' => [-40, -3, 0], 'phase_deg' => [0, 0, 0], 'warnings' => []];
    }

    public function hvsrWindows(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        $items = [];
        $win = $request['params']['windows'] ?? [];
        $mode = $win['mode'] ?? 'fixed';
        $len = (float) ($win['length_s'] ?? $request['params']['window_length_s'] ?? 60);
        if ($mode !== 'custom') {
            for ($i = 0; $i < 5; $i++) {
                $items[] = ['index' => $i, 'start_s' => $i * $len, 'end_s' => ($i + 1) * $len, 'length_s' => $len, 'accepted' => $i !== 2, 'reason' => $i === 2 ? 'sta_lta' : null,
                    'sta_lta_max' => 1.2, 'sta_lta_min' => 0.8, 'amp_ratio' => 1.5, 'has_nan' => false];
            }
        }
        foreach (($win['custom'] ?? []) as $pair) {
            $i = count($items);
            $items[] = ['index' => $i, 'start_s' => (float) $pair[0], 'end_s' => (float) $pair[1], 'length_s' => (float) $pair[1] - (float) $pair[0], 'accepted' => true, 'reason' => 'custom',
                'sta_lta_max' => 1.0, 'sta_lta_min' => 1.0, 'amp_ratio' => 1.0, 'has_nan' => false];
        }
        foreach ($items as $i => $_) {
            $items[$i]['color_index'] = $i;
        }
        foreach (($request['window_overrides'] ?? []) as $idx => $ov) {
            if (isset($items[(int) $idx])) {
                $items[(int) $idx]['accepted'] = (bool) $ov['accepted'];
                $items[(int) $idx]['reason'] = 'manual';
            }
        }
        $acc = count(array_filter($items, fn ($w) => $w['accepted']));
        $n = count($items);

        return ['windows' => $items, 'mode' => $mode, 'counts' => ['total' => $n, 'accepted' => $acc, 'rejected' => $n - $acc], 'screening_applied' => $request['params']['screening'] ?? []];
    }

    public function hvsrAnalyze(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        $dir = $request['output_dir'];
        $result = $this->fakeResult($request);

        return $this->createJob('hvsr_analyze', ['output_dir' => $dir, 'summary' => $this->summaryOf($result)], function () use ($dir, $result) {
            @mkdir($dir.'/exports', 0777, true);
            file_put_contents($dir.'/result.json', json_encode($result));
            file_put_contents($dir.'/curves.npz', 'FAKE-NPZ');
            foreach (['hvsr_mean.csv', 'hvsr_windows.csv', 'component_spectra.csv', 'summary.csv', 'azimuthal.csv'] as $f) {
                file_put_contents($dir.'/exports/'.$f, "frequency,value\n1,2\n");
            }
            file_put_contents($dir.'/exports/summary.json', json_encode($this->summaryOf($result)));
            file_put_contents($dir.'/exports/hvsr_mean.hv', "# HVSR Studio fake\n# frequency average min max\n0.5 1.1 0.9 1.3\n1.0 1.5 1.2 1.9\n");
            file_put_contents($dir.'/exports/config.json', json_encode($result['params']));
        });
    }

    public function selectPeak(string $analysisDir, ?float $frequency): array
    {
        $this->log(__FUNCTION__, compact('analysisDir', 'frequency'));
        $result = json_decode((string) @file_get_contents($analysisDir.'/result.json'), true) ?: $this->fakeResult([]);
        if ($frequency === null) {
            $result['peaks']['selected'] = ['frequency' => 2.5, 'amplitude' => 4.2, 'source' => 'automatic'];
        } else {
            $result['peaks']['selected'] = ['frequency' => $frequency, 'amplitude' => 3.1, 'source' => 'manual'];
        }
        @file_put_contents($analysisDir.'/result.json', json_encode($result));

        return $result;
    }

    public function analysisLoad(string $dir): array
    {
        $this->log(__FUNCTION__, compact('dir'));
        $json = @file_get_contents($dir.'/result.json');
        if ($json === false) {
            throw new EngineErrorException(404, 'not_found', 'result.json not found in '.$dir);
        }

        return json_decode($json, true);
    }

    public function analysisSummary(string $dir): array
    {
        return $this->summaryOf($this->analysisLoad($dir));
    }

    public function windowCurves(string $dir): array
    {
        $this->log(__FUNCTION__, compact('dir'));

        return ['frequency' => [0.5, 1, 2], 'curves' => [[1, 2, 1], [1, 3, 1]], 'accepted' => [true, true]];
    }

    public function exportFigure(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        @mkdir(dirname($request['output_path']), 0777, true);
        file_put_contents($request['output_path'], 'FAKE-'.strtoupper($request['format']));

        return ['output_path' => $request['output_path']];
    }

    public function exportReport(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        $out = $request['output_path'];

        return $this->createJob('report', ['output_path' => $out], function () use ($out) {
            @mkdir(dirname($out), 0777, true);
            file_put_contents($out, "%PDF-1.4 FAKE REPORT\n");
        });
    }

    public function job(string $jobId): array
    {
        $this->guard();
        if (! isset($this->jobs[$jobId])) {
            throw new EngineErrorException(404, 'not_found', 'Unknown job '.$jobId);
        }
        $job = &$this->jobs[$jobId];
        if (in_array($job['status'], ['queued', 'running'], true)) {
            $job['polls']++;
            if (in_array($jobId, $this->failJobs, true)) {
                $job['status'] = 'failed';
                $job['error'] = 'Simulated engine failure';
                $job['progress'] = 0.3;
            } elseif ($job['polls'] >= $this->pollsToFinish) {
                ($job['finish'])();
                $job['status'] = 'done';
                $job['progress'] = 1.0;
                $job['finished_at'] = now()->toIso8601String();
            } else {
                $job['status'] = 'running';
                $job['progress'] = $job['polls'] / max(1, $this->pollsToFinish);
            }
        }
        $copy = $job;
        unset($copy['finish'], $copy['polls']);

        return $copy;
    }

    public function cancelJob(string $jobId): array
    {
        $this->log(__FUNCTION__, compact('jobId'));
        if (isset($this->jobs[$jobId]) && in_array($this->jobs[$jobId]['status'], ['queued', 'running'], true)) {
            $this->jobs[$jobId]['status'] = 'cancelled';
        }

        return ['id' => $jobId, 'status' => $this->jobs[$jobId]['status'] ?? 'unknown'];
    }

    public function modelHvsr(array $request): array
    {
        $this->log(__FUNCTION__, $request);
        $layers = $request['layers'] ?? [];
        $n = (int) ($request['n_freq'] ?? 5);
        $fmin = (float) ($request['freq_min'] ?? 0.2);
        $fmax = (float) ($request['freq_max'] ?? 20);
        $freq = [];
        for ($i = 0; $i < $n; $i++) {
            $freq[] = $fmin * pow($fmax / $fmin, $n > 1 ? $i / ($n - 1) : 0);
        }
        $depth = 0.0;
        $echo = [];
        foreach ($layers as $l) {
            $h = $l['thickness_m'] ?? null;
            $echo[] = $l + ['depth_top_m' => $depth, 'depth_bottom_m' => $h === null ? null : $depth + $h];
            $depth += $h ?? 0;
        }

        return [
            'frequency' => $freq, 'hvsr' => array_fill(0, $n, 1.0), 't_sh' => array_fill(0, $n, 1.0), 't_p' => array_fill(0, $n, 1.0),
            'layers' => $echo, 'vs30' => 250.0, 'vseq' => ['value' => 250.0, 'depth_m' => 30.0, 'definition' => 'fake'],
            'f0_model' => $freq[intdiv($n, 2)] ?? null, 'method' => 'fake', 'notes' => ['Forward models are not unique.'],
        ];
    }

    public function importCurve(string $path): array
    {
        $this->log(__FUNCTION__, compact('path'));
        if (! is_file($path)) {
            throw new EngineErrorException(404, 'not_found', 'Curve file not found: '.$path);
        }
        $freq = [];
        $vals = [];
        foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
            if (str_starts_with(trim($line), '#')) {
                continue;
            }
            $parts = preg_split('/[\s,;]+/', trim($line));
            if (count($parts) >= 2 && is_numeric($parts[0]) && is_numeric($parts[1])) {
                $freq[] = (float) $parts[0];
                $vals[] = (float) $parts[1];
            }
        }
        if (! $freq) {
            throw new EngineErrorException(422, 'invalid_curve', 'No numeric frequency/amplitude columns found.');
        }

        return ['frequency' => $freq, 'values' => $vals, 'lower' => null, 'upper' => null, 'name' => basename($path), 'format' => str_ends_with(strtolower($path), '.hv') ? 'geopsy_hv' : 'csv'];
    }

    public function fakeResult(array $request): array
    {
        $freq = [0.5, 1.0, 2.0, 2.5, 3.0, 5.0, 10.0];
        $vals = [1.1, 1.5, 3.0, 4.2, 3.1, 1.4, 1.0];
        $curve = fn (string $band) => ['values' => $vals, 'lower' => array_map(fn ($v) => $v * 0.8, $vals), 'upper' => array_map(fn ($v) => $v * 1.25, $vals), 'band' => $band, 'sigma_ln' => array_fill(0, 7, 0.22)];

        return [
            'engine_version' => '1.0.0-fake', 'versions' => ['numpy' => 'x'], 'computed_at' => now()->toIso8601String(), 'elapsed_s' => 0.1,
            'random_seed' => $request['random_seed'] ?? 12345,
            'params' => $request['params'] ?? [],
            'input' => ['path' => $request['input_path'] ?? '', 'sha256' => str_repeat('a', 64), 'fs' => 100.0, 'n_samples' => 60000, 'duration_s' => 600.0, 'start_time' => '2025-01-01T00:00:00.000000Z', 'station' => 'SYN', 'is_synthetic' => true],
            'frequency' => $freq,
            'windows' => ['mode' => $request['params']['windows']['mode'] ?? 'fixed', 'length_s' => 60, 'overlap' => 0.5, 'count_total' => 3, 'count_accepted' => 2, 'count_rejected' => 1, 'items' => [
                ['index' => 0, 'start_s' => 0, 'end_s' => 60, 'length_s' => 60, 'accepted' => true, 'reason' => null, 'color_index' => 0],
                ['index' => 1, 'start_s' => 30, 'end_s' => 90, 'length_s' => 60, 'accepted' => false, 'reason' => 'sta_lta', 'color_index' => 1],
                ['index' => 2, 'start_s' => 60, 'end_s' => 120, 'length_s' => 60, 'accepted' => true, 'reason' => 'manual', 'color_index' => 2],
            ]],
            'time_frequency' => ['times_s' => [0, 30, 60], 'frequency' => $freq, 'matrix' => [$vals, array_fill(0, 7, null), $vals]],
            't10_hz' => 10 / 60,
            'curves' => ['selected' => 'geometric', 'geometric' => $curve('exp(mean(ln HV) ± std(ln HV, ddof=1))'), 'arithmetic' => $curve('mean ± std'), 'median' => $curve('16th–84th percentile')],
            'components' => ['n' => $vals, 'e' => $vals, 'z' => array_fill(0, 7, 1.0), 'h' => $vals],
            'directional' => null,
            'masking' => ['policy' => 'fake', 'bins_masked_any_window' => 0, 'invalid_bins' => [], 'min_valid_windows' => 3],
            'peaks' => ['search_range' => [0.5, 20], 'candidates' => [['frequency' => 2.5, 'amplitude' => 4.2, 'prominence' => 3.0, 'rank' => 1]], 'selected' => ['frequency' => 2.5, 'amplitude' => 4.2, 'source' => 'automatic'], 'status' => 'clear', 'message' => 'Clear peak.'],
            'peak_variability' => ['window_f0' => [2.4, 2.5, 2.6], 'window_a0' => [4, 4.2, 4.4], 'n' => 3, 'median' => 2.5, 'p16' => 2.4, 'p84' => 2.6, 'std' => 0.1, 'std_ln' => 0.04, 'definition' => 'fake', 'bootstrap' => null],
            'sesame' => ['reference' => 'SESAME (2004) D23.12', 'f0' => 2.5, 'a0' => 4.2, 'reliability' => [], 'clarity' => [], 'reliability_passed' => true, 'clarity_passed_count' => 6, 'clarity_passed' => true],
            'quality_flags' => [],
            'azimuthal' => null,
            'interpretation_notes' => ['HVSR amplitude is not a direct measure of site amplification.'],
        ];
    }

    public function summaryOf(array $result): array
    {
        return [
            'peaks' => $result['peaks'] ?? null,
            'sesame' => $result['sesame'] ?? null,
            'windows' => array_intersect_key($result['windows'] ?? [], array_flip(['length_s', 'overlap', 'count_total', 'count_accepted', 'count_rejected'])),
            'quality_flags' => $result['quality_flags'] ?? [],
            'peak_variability' => array_diff_key($result['peak_variability'] ?? [], array_flip(['window_f0', 'window_a0'])),
            'random_seed' => $result['random_seed'] ?? null,
            'engine_version' => $result['engine_version'] ?? null,
        ];
    }

    private function createJob(string $kind, array $result, callable $finish): array
    {
        $id = 'fakejob-'.(++$this->jobCounter).'-'.Str::lower(Str::random(6));
        $this->jobs[$id] = [
            'id' => $id, 'kind' => $kind, 'status' => 'queued', 'progress' => 0.0, 'message' => 'queued', 'result' => $result, 'error' => null,
            'created_at' => now()->toIso8601String(), 'started_at' => null, 'finished_at' => null, 'finish' => $finish, 'polls' => 0,
        ];

        return ['id' => $id, 'kind' => $kind, 'status' => 'queued', 'progress' => 0.0, 'message' => 'queued'];
    }

    private function log(string $method, array $payload): void
    {
        $this->guard();
        $this->calls[] = ['method' => $method, 'payload' => $payload];
    }

    private function guard(): void
    {
        if ($this->down) {
            throw new EngineUnavailableException('Could not reach the processing engine (fake down).');
        }
    }
}
