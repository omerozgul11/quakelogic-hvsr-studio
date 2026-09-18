<?php

namespace Database\Seeders;

use App\Models\ProcessingPreset;
use Illuminate\Database\Seeder;

class PresetSeeder extends Seeder
{
    public static function builtin(): array
    {
        $base = [
            'overlap' => 0.5,
            'screening' => [
                'enabled' => true,
                'sta_lta' => ['enabled' => true, 'sta_s' => 1.0, 'lta_s' => 30.0, 'min_ratio' => 0.2, 'max_ratio' => 2.5],
                'amplitude' => ['enabled' => false, 'max_ratio_to_rms' => 5.0],
            ],
            'detrend' => 'linear',
            'taper_percent' => 5,
            'smoothing' => ['type' => 'konno_ohmachi', 'bandwidth' => 40],
            'n_freq' => 300,
            'horizontal_method' => 'geometric_mean',
            'combination_stage' => 'after_smoothing',
            'mean_method' => 'geometric',
            'vertical_floor' => ['relative' => 1e-6, 'absolute' => 1e-12],
            'min_valid_windows' => 3,
            'bootstrap' => ['enabled' => true, 'n_resamples' => 200],
            'azimuthal' => ['enabled' => false, 'step_deg' => 10],
            'sesame' => true,
        ];

        return [
            [
                'name' => 'Standard ambient noise (60 s, KO 40)',
                'description' => 'Mean removal + linear detrend, 60 s windows with 50 % overlap, STA/LTA transient screening, Konno–Ohmachi b = 40, 0.2–30 Hz, geometric-mean horizontal, log-mean curve. Suitable for most site-characterisation measurements.',
                'steps' => [
                    ['op' => 'demean', 'enabled' => true, 'params' => []],
                    ['op' => 'detrend', 'enabled' => true, 'params' => []],
                ],
                'hvsr_params' => $base + ['window_length_s' => 60, 'freq_min' => 0.2, 'freq_max' => 30, 'peak' => ['search_min' => 0.5, 'search_max' => 20, 'min_prominence' => 0.0]],
            ],
            [
                'name' => 'Short windows (25 s)',
                'description' => '25 s windows for short or transient-rich records (resolves peaks above ~0.4 Hz). Same screening and smoothing as the standard preset.',
                'steps' => [
                    ['op' => 'demean', 'enabled' => true, 'params' => []],
                    ['op' => 'detrend', 'enabled' => true, 'params' => []],
                ],
                'hvsr_params' => $base + ['window_length_s' => 25, 'freq_min' => 0.4, 'freq_max' => 40, 'peak' => ['search_min' => 1.0, 'search_max' => 30, 'min_prominence' => 0.0]],
            ],
            [
                'name' => 'Low-frequency site (120 s, 0.1–10 Hz)',
                'description' => '120 s windows for deep-basin or soft-soil sites with expected resonance below 1 Hz. Requires long records (≥ 30 min recommended). Screening thresholds relaxed slightly.',
                'steps' => [
                    ['op' => 'demean', 'enabled' => true, 'params' => []],
                    ['op' => 'detrend', 'enabled' => true, 'params' => []],
                ],
                'hvsr_params' => array_replace_recursive($base, ['screening' => ['sta_lta' => ['lta_s' => 60.0, 'max_ratio' => 3.0]]])
                    + ['window_length_s' => 120, 'freq_min' => 0.1, 'freq_max' => 10, 'peak' => ['search_min' => 0.15, 'search_max' => 8, 'min_prominence' => 0.0]],
            ],
        ];
    }

    public function run(): void
    {
        foreach (self::builtin() as $preset) {
            ProcessingPreset::query()->updateOrCreate(
                ['project_id' => null, 'name' => $preset['name']],
                ['description' => $preset['description'], 'steps' => $preset['steps'], 'hvsr_params' => $preset['hvsr_params']],
            );
        }
    }
}
