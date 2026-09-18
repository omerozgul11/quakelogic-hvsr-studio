<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Project;
use App\Services\Engine\EngineClientInterface;
use App\Services\Projects\ProjectStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;

/**
 * Loads an external H/V curve (Geopsy .hv or CSV/TXT) for overlay / comparison.
 */
class CurveController extends Controller
{
    public function store(Request $request, Project $project, EngineClientInterface $engine, ProjectStorage $storage): JsonResponse
    {
        $request->validate(['file' => ['required', 'file', 'max:20480']]);
        $file = $request->file('file');
        $name = $storage->safeFilename($file->getClientOriginalName());
        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        abort_unless(in_array($ext, ['hv', 'csv', 'txt', 'dat'], true), 422, 'Only .hv, .csv, .txt and .dat curve files are accepted.');

        $dir = $storage->uploadDir($project, 'curve-'.Str::lower(Str::random(12)));
        File::ensureDirectoryExists($dir);
        $file->move($dir, $name);
        $path = $dir.'/'.$name;
        try {
            $curve = $engine->importCurve($path);
        } finally {
            File::deleteDirectory($dir);
        }
        $curve['name'] = $curve['name'] ?? pathinfo($name, PATHINFO_FILENAME);

        return response()->json($curve);
    }
}
