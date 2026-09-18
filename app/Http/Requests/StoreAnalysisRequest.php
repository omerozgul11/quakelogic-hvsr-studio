<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreAnalysisRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['name' => ['nullable', 'string', 'max:160'], 'run_id' => ['nullable', 'string', 'size:26'], 'params' => ['required', 'array'], 'window_overrides' => ['nullable', 'array'], 'manual_peak' => ['nullable', 'array'], 'manual_peak.frequency' => ['required_with:manual_peak', 'numeric', 'gt:0'], 'random_seed' => ['nullable', 'integer', 'min:0']];
    }
}
