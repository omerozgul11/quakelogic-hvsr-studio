<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreRunRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['name' => ['nullable', 'string', 'max:160'], 'steps' => ['required', 'array', 'min:1'], 'steps.*.op' => ['required', 'string', 'in:demean,detrend,polynomial,filter,notch,taper,crop,resample,rotate,remove_response'], 'steps.*.enabled' => ['nullable', 'boolean'], 'steps.*.params' => ['nullable', 'array']];
    }
}
