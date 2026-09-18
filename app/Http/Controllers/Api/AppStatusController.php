<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Setting;
use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\EngineUnavailableException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;

class AppStatusController extends Controller
{
    public function status(EngineClientInterface $engine): JsonResponse
    {
        try {
            $health = $engine->health();
        } catch (EngineUnavailableException $e) {
            $health = ['status' => 'down', 'hint' => $e->getMessage()];
        } catch (\Throwable $e) {
            $health = ['status' => 'error', 'hint' => $e->getMessage()];
        }

        return response()->json([
            'app_version' => config('hvsr.app_version'),
            'app_name' => config('app.name'),
            'engine' => $health,
            'engine_url' => config('hvsr.engine_url'),
            'data_dir' => config('hvsr.data_dir'),
            'theme_default' => Setting::get('theme_default', 'system'),
            'php_version' => PHP_VERSION,
            'heartbeat_age_s' => self::age('app.heartbeat'),
            'goodbye_age_s' => self::age('app.goodbye'),
        ]);
    }

    /** The interface calls this every few seconds while a window is open; the launcher watches it. */
    public function heartbeat(): JsonResponse
    {
        Cache::put('app.heartbeat', microtime(true), 120);
        Cache::forget('app.goodbye');

        return response()->json(['ok' => true]);
    }

    /** Sent by the interface when its window/tab is being closed. */
    public function goodbye(): JsonResponse
    {
        Cache::put('app.goodbye', microtime(true), 120);

        return response()->json(['ok' => true]);
    }

    private static function age(string $key): ?float
    {
        $stamp = Cache::get($key);

        return is_numeric($stamp) ? round(microtime(true) - (float) $stamp, 1) : null;
    }

    public function settings(): JsonResponse
    {
        return response()->json($this->payload());
    }

    public function updateSettings(Request $request): JsonResponse
    {
        $data = $request->validate([
            'theme_default' => ['nullable', 'in:light,dark,system'],
            'unit_system' => ['nullable', 'in:metric,us'],
            'default_preset_id' => ['nullable', 'string', 'size:26'],
            'plot_max_points' => ['nullable', 'integer', 'min:500', 'max:50000'],
            'show_synthetic_banner' => ['nullable', 'boolean'],
        ]);
        foreach ($data as $key => $value) {
            Setting::put($key, $value);
        }

        return response()->json($this->payload());
    }

    private function payload(): array
    {
        return array_merge([
            'theme_default' => 'system',
            'unit_system' => 'metric',
            'default_preset_id' => null,
            'plot_max_points' => 4000,
            'show_synthetic_banner' => true,
        ], Setting::all_(), [
            'engine_url' => config('hvsr.engine_url'),
            'data_dir' => config('hvsr.data_dir'),
            'app_version' => config('hvsr.app_version'),
        ]);
    }
}
