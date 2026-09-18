<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Setting;
use App\Services\Engine\EngineClientInterface;
use App\Services\Engine\EngineUnavailableException;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

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
        ]);
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
