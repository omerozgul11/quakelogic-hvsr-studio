<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;

/**
 * Licence status and activation. The engine owns the signed-file verification and the trial record;
 * Laravel only forwards the file (never stores it) and the status.
 */
class LicenseController extends Controller
{
    public function status(EngineClientInterface $engine): JsonResponse
    {
        return response()->json($engine->licenseStatus());
    }

    public function install(Request $request, EngineClientInterface $engine): JsonResponse
    {
        $request->validate(['file' => ['required', 'file', 'max:64']]);
        $file = $request->file('file');
        $ext = strtolower($file->getClientOriginalExtension());
        abort_unless(in_array($ext, ['qlicense', 'json', 'txt'], true), 422, 'Choose the .qlicense file you received from QuakeLogic.');

        $dir = storage_path('app/license-staging/'.Str::lower(Str::random(12)));
        File::ensureDirectoryExists($dir);
        $file->move($dir, 'license.qlicense');
        try {
            $status = $engine->installLicense($dir.'/license.qlicense');
        } finally {
            File::deleteDirectory($dir);
        }

        return response()->json($status);
    }
}
