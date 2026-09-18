<?php

namespace App\Services\Projects;

use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Models\Batch;
use App\Models\BatchItem;
use App\Models\ProcessingPreset;
use App\Models\ProcessingRun;
use App\Models\Project;
use App\Models\Recording;
use App\Models\RecordingFile;
use App\Models\Station;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;
use ZipArchive;

/**
 * Backup = zip of the project folder (under "project/") + database.json with every row of the project.
 * Restore recreates the project under a free slug, remaps ids/paths and moves the folder into place.
 */
class ProjectBackupService
{
    public const FORMAT = 'quakelogic-hvsr-studio-backup/1';

    private const PATH_COLUMNS = [
        'recordings' => ['canonical_path'],
        'recording_files' => ['stored_path'],
        'processing_runs' => ['output_path'],
        'analyses' => ['result_dir', 'report_path'],
    ];

    public function __construct(private readonly ProjectStorage $storage) {}

    public function backup(Project $project): string
    {
        $dir = $this->storage->projectDir($project);
        $tmp = $this->tmpDir();
        $zipPath = $tmp.'/'.$project->slug.'-backup.zip';
        $zip = new ZipArchive;
        if ($zip->open($zipPath, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
            throw new \RuntimeException('Could not create the backup archive.');
        }
        $zip->addFromString('database.json', json_encode($this->dump($project, $dir), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
        if (is_dir($dir)) {
            foreach (File::allFiles($dir, true) as $file) {
                $rel = str_replace('\\', '/', substr($file->getPathname(), strlen($dir) + 1));
                if (str_starts_with($rel, 'uploads/')) {
                    continue;
                }
                $zip->addFile($file->getPathname(), 'project/'.$rel);
            }
        }
        $zip->close();
        ActivityLog::record($project->id, 'project.backup', $project, ['file' => basename($zipPath)]);

        return $zipPath;
    }

    public function dump(Project $project, string $dir): array
    {
        $rows = fn ($query) => $query->get()->map(fn ($m) => $m->getAttributes())->values()->all();

        return [
            'format' => self::FORMAT,
            'app_version' => config('hvsr.app_version'),
            'created_at' => now()->toIso8601String(),
            'project_dir' => $dir,
            'project' => $project->getAttributes(),
            'stations' => $rows($project->stations()),
            'recordings' => $rows($project->recordings()),
            'recording_files' => $rows(RecordingFile::query()->whereIn('recording_id', $project->recordings()->select('id'))),
            'presets' => $rows($project->presets()),
            'processing_runs' => $rows($project->runs()),
            'analyses' => $rows($project->analyses()),
            'batches' => $rows($project->batches()),
            'batch_items' => $rows(BatchItem::query()->whereIn('batch_id', $project->batches()->select('id'))),
            'activity_log' => $rows($project->activity()),
        ];
    }

    public function restore(string $zipPath): Project
    {
        $zip = new ZipArchive;
        if ($zip->open($zipPath) !== true) {
            throw ValidationException::withMessages(['file' => 'The file is not a valid zip archive.']);
        }
        $json = $zip->getFromName('database.json');
        if ($json === false) {
            throw ValidationException::withMessages(['file' => 'database.json is missing from the archive; this is not an HVSR Studio backup.']);
        }
        $dump = json_decode($json, true);
        if (! is_array($dump) || ($dump['format'] ?? null) !== self::FORMAT || empty($dump['project']['name'])) {
            throw ValidationException::withMessages(['file' => 'database.json is not in the HVSR Studio backup format.']);
        }

        $extract = $this->tmpDir();
        $zip->extractTo($extract);
        $zip->close();

        return DB::transaction(function () use ($dump, $extract) {
            $this->storage->ensureDataDir();
            $old = $dump['project'];
            $slug = $this->storage->uniqueSlug($old['name']);
            $project = Project::create([
                'name' => $old['name'],
                'slug' => $slug,
                'folder' => $slug,
                'description' => $old['description'] ?? null,
                'settings' => $this->json($old['settings'] ?? null),
                'ulid' => $this->freeUlid(Project::class, $old['ulid'] ?? null),
            ]);
            $newDir = $this->storage->createProjectFolder($project);
            $source = $extract.'/project';
            if (is_dir($source)) {
                File::copyDirectory($source, $newDir);
            }
            File::deleteDirectory($extract);
            $oldDir = rtrim(str_replace('\\', '/', (string) ($dump['project_dir'] ?? '')), '/');
            $repath = fn (?string $p) => $p === null ? null : ($oldDir !== '' && str_starts_with(str_replace('\\', '/', $p), $oldDir) ? $newDir.substr(str_replace('\\', '/', $p), strlen($oldDir)) : $p);

            $stations = $this->insert(Station::class, $dump['stations'] ?? [], ['project_id' => $project->id]);
            $recordings = $this->insert(Recording::class, $dump['recordings'] ?? [], ['project_id' => $project->id], [
                'station_id' => $stations,
            ], self::PATH_COLUMNS['recordings'], $repath);
            $this->insert(RecordingFile::class, $dump['recording_files'] ?? [], [], ['recording_id' => $recordings], self::PATH_COLUMNS['recording_files'], $repath);
            $presets = $this->insert(ProcessingPreset::class, $dump['presets'] ?? [], ['project_id' => $project->id]);
            $runs = $this->insert(ProcessingRun::class, $dump['processing_runs'] ?? [], ['project_id' => $project->id], ['recording_id' => $recordings], self::PATH_COLUMNS['processing_runs'], $repath);
            $analyses = $this->insert(Analysis::class, $dump['analyses'] ?? [], ['project_id' => $project->id], ['recording_id' => $recordings, 'processing_run_id' => $runs], self::PATH_COLUMNS['analyses'], $repath);
            $batches = $this->insert(Batch::class, $dump['batches'] ?? [], ['project_id' => $project->id], ['preset_id' => $presets]);
            $this->insert(BatchItem::class, $dump['batch_items'] ?? [], [], ['batch_id' => $batches, 'recording_id' => $recordings, 'processing_run_id' => $runs, 'analysis_id' => $analyses]);
            foreach ($dump['activity_log'] ?? [] as $row) {
                ActivityLog::query()->insert([
                    'project_id' => $project->id,
                    'subject_type' => $row['subject_type'] ?? null,
                    'subject_id' => $row['subject_id'] ?? null,
                    'action' => $row['action'] ?? 'unknown',
                    'details' => is_array($row['details'] ?? null) ? json_encode($row['details']) : ($row['details'] ?? null),
                    'created_at' => $row['created_at'] ?? now(),
                ]);
            }
            ActivityLog::record($project->id, 'project.restored', $project, ['from' => $old['slug'] ?? null, 'app_version' => $dump['app_version'] ?? null]);

            return $project;
        });
    }

    /**
     * Insert rows with fresh auto-increment ids; returns old id → new id map.
     *
     * @param  array<string, array<int,int>>  $fkMaps  column => old→new map
     */
    private function insert(string $model, array $rows, array $overrides, array $fkMaps = [], array $pathColumns = [], ?callable $repath = null): array
    {
        $map = [];
        foreach ($rows as $row) {
            $oldId = $row['id'] ?? null;
            unset($row['id']);
            foreach ($fkMaps as $col => $m) {
                if (array_key_exists($col, $row)) {
                    $row[$col] = $row[$col] === null ? null : ($m[$row[$col]] ?? null);
                }
            }
            foreach ($pathColumns as $col) {
                if (array_key_exists($col, $row) && $repath) {
                    $row[$col] = $repath($row[$col]);
                }
            }
            if (array_key_exists('ulid', $row)) {
                $row['ulid'] = $this->freeUlid($model, $row['ulid']);
            }
            $row = array_merge($row, $overrides);
            $instance = new $model;
            foreach ($row as $k => $v) {
                $instance->setRawAttributes(array_merge($instance->getAttributes(), [$k => $v]));
            }
            $instance->save();
            if ($oldId !== null) {
                $map[$oldId] = $instance->getKey();
            }
        }

        return $map;
    }

    private function freeUlid(string $model, ?string $ulid): string
    {
        if ($ulid && ! $model::query()->where('ulid', $ulid)->exists()) {
            return $ulid;
        }

        return (string) Str::ulid();
    }

    private function json(mixed $value): mixed
    {
        return is_string($value) ? (json_decode($value, true) ?? []) : ($value ?? []);
    }

    private function tmpDir(): string
    {
        $dir = $this->storage->dataDir().'/tmp/'.Str::lower(Str::random(12));
        File::ensureDirectoryExists($dir);

        return $dir;
    }
}
