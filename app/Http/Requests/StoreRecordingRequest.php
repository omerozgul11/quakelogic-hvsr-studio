<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreRecordingRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['name' => ['required', 'string', 'max:160'], 'station_id' => ['nullable', 'string', 'size:26'], 'notes' => ['nullable', 'string', 'max:5000'], 'upload_ids' => ['required', 'array', 'min:1', 'max:3'], 'upload_ids.*' => ['string', 'size:26'], 'import' => ['required', 'array'], 'import.format' => ['required', 'in:ascii,mseed,saf,seismic'], 'import.saf' => ['nullable', 'array'], 'import.ascii' => ['nullable', 'array'], 'import.mseed' => ['nullable', 'array'], 'import.metadata' => ['nullable', 'array'], 'import.roles' => ['nullable', 'array'], 'import.roles.*' => ['in:all,n,e,z'], 'import.sources' => ['nullable', 'array'], 'import.sources.*.upload_id' => ['required_with:import.sources', 'string', 'size:26'], 'import.sources.*.role' => ['required_with:import.sources', 'in:all,n,e,z']];
    }
}
