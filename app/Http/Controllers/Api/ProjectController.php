<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreProjectRequest;
use App\Http\Requests\UpdateProjectRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\Project;
use App\Services\Engine\JobSync;
use App\Services\Projects\ProjectBackupService;
use App\Services\Projects\ProjectStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class ProjectController extends Controller
{
    public function __construct(private readonly ProjectStorage $storage) {}

    public function index(): JsonResponse
    {
        return response()->json(Project::query()->latest('updated_at')->get()->map(fn ($p) => Json::project($p))->values());
    }

    public function store(StoreProjectRequest $request): JsonResponse
    {
        $this->storage->ensureDataDir();
        $data = $request->validated();
        $slug = $this->storage->uniqueSlug($data['name']);
        $project = Project::create([
            'name' => $data['name'],
            'slug' => $slug,
            'folder' => $slug,
            'description' => $data['description'] ?? null,
            'settings' => $data['settings'] ?? [],
        ]);
        $this->storage->createProjectFolder($project);
        ActivityLog::record($project->id, 'project.created', $project, ['name' => $project->name]);

        return response()->json(Json::project($project, true), 201);
    }

    public function show(Project $project, JobSync $jobs): JsonResponse
    {
        // Refresh the status of anything still running so the tree never shows stale states.
        try {
            foreach ($project->runs()->whereIn('status', ['queued', 'running'])->get() as $run) {
                $jobs->syncRun($run);
            }
            foreach ($project->analyses()->whereIn('status', ['queued', 'running'])->get() as $analysis) {
                $jobs->syncAnalysis($analysis);
            }
        } catch (\Throwable) {
            // Engine unavailable: serve the stored states; the SPA shows the engine status separately.
        }
        $project->load(['stations', 'recordings.files', 'recordings.station']);

        return response()->json(Json::project($project, true));
    }

    public function update(UpdateProjectRequest $request, Project $project): JsonResponse
    {
        $project->update($request->validated());
        ActivityLog::record($project->id, 'project.updated', $project, $request->validated());

        return response()->json(Json::project($project, true));
    }

    public function destroy(Project $project): JsonResponse
    {
        $this->storage->deleteProjectFolder($project);
        $project->delete();

        return response()->json(['deleted' => true]);
    }

    public function backup(Project $project, ProjectBackupService $backups): BinaryFileResponse
    {
        $zip = $backups->backup($project);

        return response()->download($zip, basename($zip))->deleteFileAfterSend(true);
    }

    public function restore(Request $request, ProjectBackupService $backups): JsonResponse
    {
        $request->validate(['file' => ['required', 'file', 'max:4194304']]);
        $project = $backups->restore($request->file('file')->getRealPath());

        return response()->json(Json::project($project->fresh(['stations', 'recordings.files', 'recordings.station']), true), 201);
    }

    public function history(Project $project): JsonResponse
    {
        return response()->json($project->activity()->latest('id')->limit(500)->get()->map(fn ($l) => Json::activity($l))->values());
    }
}
