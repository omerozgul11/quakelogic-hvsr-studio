<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreBatchRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['name' => ['required', 'string', 'max:160'], 'preset_id' => ['nullable', 'string', 'size:26'], 'recording_ids' => ['required', 'array', 'min:1'], 'recording_ids.*' => ['string', 'size:26'], 'run_steps' => ['nullable', 'boolean']];
    }
}
