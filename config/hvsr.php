<?php

$resolve = static function (?string $path, string $default): string {
    $path = $path === null || $path === '' ? $default : $path;
    if (! preg_match('#^(/|[A-Za-z]:[\\\\/]|\\\\\\\\)#', $path)) {
        $path = base_path($path);
    }

    return rtrim(str_replace('\\', '/', $path), '/');
};

$dataDir = $resolve(env('HVSR_DATA_DIR'), base_path('data'));

return [
    'app_version' => '1.0.0',
    'data_dir' => $dataDir,
    'projects_dir' => $dataDir.'/projects',
    'engine_url' => rtrim((string) env('HVSR_ENGINE_URL', 'http://127.0.0.1:8765'), '/'),
    'engine_token' => env('HVSR_ENGINE_TOKEN') ?: null,
    'max_upload_mb' => (int) env('HVSR_MAX_UPLOAD_MB', 2048),
    'engine_timeout' => (int) env('HVSR_ENGINE_TIMEOUT', 15),
    'engine_compute_timeout' => (int) env('HVSR_ENGINE_COMPUTE_TIMEOUT', 120),
];
