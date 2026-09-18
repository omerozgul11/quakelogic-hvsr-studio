<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreStationRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['code' => ['required', 'string', 'max:32'], 'name' => ['nullable', 'string', 'max:120'], 'latitude' => ['nullable', 'numeric', 'between:-90,90'], 'longitude' => ['nullable', 'numeric', 'between:-180,180'], 'elevation' => ['nullable', 'numeric'], 'orientation_deg' => ['nullable', 'numeric', 'between:-360,360'], 'notes' => ['nullable', 'string', 'max:5000']];
    }
}
