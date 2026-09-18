<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class UpdatePresetRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['name' => ['sometimes', 'required', 'string', 'max:120'], 'description' => ['nullable', 'string', 'max:2000'], 'steps' => ['nullable', 'array'], 'steps.*.op' => ['required', 'string'], 'hvsr_params' => ['nullable', 'array']];
    }
}
