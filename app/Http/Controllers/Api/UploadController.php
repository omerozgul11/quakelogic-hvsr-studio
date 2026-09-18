<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Serializers\Json;
use App\Models\Project;
use App\Services\Projects\RecordingImportService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class UploadController extends Controller
{
    public function store(Request $request, Project $project, RecordingImportService $import): JsonResponse
    {
        $maxKb = (int) config('hvsr.max_upload_mb', 2048) * 1024;
        $request->validate([
            'files' => ['required', 'array', 'min:1', 'max:20'],
            'files.*' => ['required', 'file', 'max:'.$maxKb],
        ]);

        $uploads = $import->stageUploads($project, $request->file('files'));

        return response()->json(array_map(fn ($u) => Json::upload($u), $uploads), 201);
    }
}
