<?php

namespace App\Services\Projects;

use App\Models\ActivityLog;
use App\Models\Project;
use App\Models\Recording;
use App\Models\Station;
use App\Models\Upload;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\File;
use Illuminate\Validation\ValidationException;

class RecordingImportService
{
    public function __construct(
        private readonly EngineClientInterface $engine,
        private readonly ProjectStorage $storage,
    ) {}

    /** @param UploadedFile[] $files */
    public function stageUploads(Project $project, array $files): array
    {
        $out = [];
        foreach ($files as $file) {
            $upload = new Upload([
                'project_id' => $project->id,
                'original_name' => $this->storage->safeFilename($file->getClientOriginalName()),
                'stored_path' => '',
                'size_bytes' => $file->getSize() ?: 0,
            ]);
            $upload->save();

            $dir = $this->storage->uploadDir($project, $upload->ulid);
            File::ensureDirectoryExists($dir);
            $file->move($dir, $upload->original_name);
            $path = $dir.'/'.$upload->original_name;

            $inspect = $this->engine->inspectFile($path);
            $upload->update([
                'stored_path' => $path,
                'sha256' => $inspect['sha256'] ?? $this->storage->sha256($path),
                'size_bytes' => filesize($path) ?: 0,
                'inspect' => $inspect,
            ]);
            $out[] = $upload;
        }

        return $out;
    }

    /**
     * @param  array  $data  {name, station_id?, upload_ids[], import{format, ascii?, mseed?, metadata?, roles?}}
     */
    public function createRecording(Project $project, array $data): Recording
    {
        $uploads = Upload::query()
            ->where('project_id', $project->id)
            ->whereIn('ulid', $data['upload_ids'])
            ->where('consumed', false)
            ->get()
            ->keyBy('ulid');

        if ($uploads->count() !== count(array_unique($data['upload_ids']))) {
            throw ValidationException::withMessages(['upload_ids' => 'One or more uploads are unknown or already used.']);
        }

        $station = null;
        if (! empty($data['station_id'])) {
            $station = Station::query()->where('project_id', $project->id)->where('ulid', $data['station_id'])->first();
            if (! $station) {
                throw ValidationException::withMessages(['station_id' => 'Unknown station.']);
            }
        }

        $import = $data['import'];
        $roles = $import['roles'] ?? [];
        // The SPA sends roles as a list of {upload_id, role} sources; accept both shapes.
        foreach ($import['sources'] ?? [] as $source) {
            if (isset($source['upload_id'], $source['role'])) {
                $roles[$source['upload_id']] = $source['role'];
            }
        }

        $recording = new Recording([
            'project_id' => $project->id,
            'station_id' => $station?->id,
            'name' => $data['name'],
            'status' => 'pending',
            'format' => $import['format'],
            'is_synthetic' => (bool) ($import['metadata']['is_synthetic'] ?? false),
            'notes' => $data['notes'] ?? null,
        ]);
        $recording->save();

        $sourcesDir = $this->storage->sourcesDir($recording);
        File::ensureDirectoryExists($sourcesDir);
        $sources = [];
        $fileRows = [];
        foreach ($data['upload_ids'] as $uid) {
            $upload = $uploads[$uid];
            $target = $sourcesDir.'/'.$upload->original_name;
            if (file_exists($target)) {
                $target = $sourcesDir.'/'.$uid.'_'.$upload->original_name;
            }
            // Copy, not move: a blocked import must leave the staged uploads intact so the
            // user can correct the mapping and try again without re-uploading.
            File::copy($upload->stored_path, $target);
            $role = $roles[$uid] ?? 'all';
            $sources[] = ['path' => $target, 'role' => $role];
            $fileRows[] = ['original_name' => $upload->original_name, 'stored_path' => $target, 'size_bytes' => $upload->size_bytes, 'sha256' => $upload->sha256 ?: $this->storage->sha256($target), 'role' => $role];
        }

        $metadata = $import['metadata'] ?? [];
        if ($station) {
            $metadata += ['station' => $station->code];
            if ($station->orientation_deg !== null && ! isset($metadata['orientation_deg'])) {
                $metadata['orientation_deg'] = $station->orientation_deg;
            }
        }
        $metadata['is_synthetic'] = $recording->is_synthetic;

        $request = [
            'recording_id' => $recording->ulid,
            'output_path' => $this->storage->tracePath($recording),
            'sources' => $sources,
            'format' => $import['format'],
            'ascii' => $import['ascii'] ?? null,
            'mseed' => $import['mseed'] ?? null,
            'saf' => $import['saf'] ?? null,
            'metadata' => $metadata,
        ];

        try {
            $response = $this->engine->importRecording($request);
        } catch (\Throwable $e) {
            $this->storage->deleteRecordingFiles($recording);
            $recording->delete();
            throw $e;
        }

        $validation = $response['validation'] ?? ['blocking' => true, 'issues' => []];
        if (! ($response['ok'] ?? false)) {
            $this->storage->deleteRecordingFiles($recording);
            $recording->delete();
            throw new ImportBlockedException($validation);
        }

        $meta = $response['meta'] ?? [];
        $recording->update([
            'status' => 'ready',
            'sample_rate' => $meta['fs'] ?? null,
            'start_time' => $meta['start_time'] ?? null,
            'duration_s' => $meta['duration_s'] ?? null,
            'n_samples' => $meta['n_samples'] ?? null,
            'units' => $meta['units'] ?? null,
            'unit_kind' => $meta['unit_kind'] ?? null,
            'import_settings' => $import,
            'validation' => $validation,
            'canonical_path' => $request['output_path'],
            'meta' => $meta,
        ]);
        foreach ($fileRows as $row) {
            $recording->files()->create($row);
        }
        foreach ($uploads as $upload) {
            $upload->update(['consumed' => true]);
            File::deleteDirectory(dirname($upload->stored_path));
        }

        ActivityLog::record($project->id, 'recording.imported', $recording, [
            'name' => $recording->name, 'files' => array_column($fileRows, 'original_name'), 'format' => $import['format'],
            'warnings' => count(array_filter($validation['issues'] ?? [], fn ($i) => ($i['severity'] ?? '') === 'warning')),
        ]);

        return $recording->fresh(['files', 'station']);
    }

    public function delete(Recording $recording): void
    {
        $this->storage->deleteRecordingFiles($recording);
        foreach ($recording->runs as $run) {
            $dir = $this->storage->runDir($recording->project, $run->ulid);
            if (is_dir($dir)) {
                File::deleteDirectory($dir);
            }
        }
        foreach ($recording->analyses as $analysis) {
            $dir = $this->storage->analysisDir($recording->project, $analysis->ulid);
            if (is_dir($dir)) {
                File::deleteDirectory($dir);
            }
        }
        ActivityLog::record($recording->project_id, 'recording.deleted', $recording, ['name' => $recording->name]);
        $recording->delete();
    }
}
