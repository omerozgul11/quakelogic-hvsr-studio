<?php

namespace App\Services\Projects;

use App\Models\Project;
use App\Models\Recording;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use InvalidArgumentException;

/**
 * Owns the on-disk project folder layout (docs/architecture.md, "Project folder layout").
 * All paths returned are absolute, forward-slash normalised and guaranteed to live under the data dir.
 */
class ProjectStorage
{
    public function dataDir(): string
    {
        return $this->normalize((string) config('hvsr.data_dir'));
    }

    public function projectsDir(): string
    {
        return $this->normalize((string) config('hvsr.projects_dir'));
    }

    public function ensureDataDir(): void
    {
        File::ensureDirectoryExists($this->projectsDir());
    }

    public function uniqueSlug(string $name, ?int $ignoreId = null): string
    {
        $base = Str::slug($name) ?: 'project';
        $slug = $base;
        $i = 2;
        while (Project::query()->where('slug', $slug)->when($ignoreId, fn ($q) => $q->where('id', '!=', $ignoreId))->exists()
            || ($ignoreId === null && is_dir($this->projectsDir().'/'.$slug))) {
            $slug = $base.'-'.$i++;
        }

        return $slug;
    }

    public function createProjectFolder(Project $project): string
    {
        $dir = $this->projectDir($project);
        foreach (['', 'uploads', 'sources', 'traces', 'runs', 'analyses'] as $sub) {
            File::ensureDirectoryExists(rtrim($dir.'/'.$sub, '/'));
        }
        File::put($dir.'/project.json', json_encode([
            'name' => $project->name,
            'ulid' => $project->ulid,
            'slug' => $project->slug,
            'created_at' => $project->created_at?->toIso8601String(),
            'app_version' => config('hvsr.app_version'),
        ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

        return $dir;
    }

    public function deleteProjectFolder(Project $project): void
    {
        $dir = $this->projectDir($project);
        if (is_dir($dir)) {
            File::deleteDirectory($dir);
        }
    }

    public function projectDir(Project $project): string
    {
        return $this->safe($this->projectsDir().'/'.$project->folder);
    }

    public function uploadDir(Project $project, string $uploadUlid): string
    {
        return $this->safe($this->projectDir($project).'/uploads/'.$uploadUlid);
    }

    public function sourcesDir(Recording $recording): string
    {
        return $this->safe($this->projectDir($recording->project).'/sources/'.$recording->ulid);
    }

    public function tracePath(Recording $recording): string
    {
        return $this->safe($this->projectDir($recording->project).'/traces/'.$recording->ulid.'.npz');
    }

    public function runDir(Project $project, string $runUlid): string
    {
        return $this->safe($this->projectDir($project).'/runs/'.$runUlid);
    }

    public function analysisDir(Project $project, string $analysisUlid): string
    {
        return $this->safe($this->projectDir($project).'/analyses/'.$analysisUlid);
    }

    public function exportsDir(Project $project, string $analysisUlid): string
    {
        return $this->analysisDir($project, $analysisUlid).'/exports';
    }

    public function deleteRecordingFiles(Recording $recording): void
    {
        foreach ([$this->sourcesDir($recording)] as $dir) {
            if (is_dir($dir)) {
                File::deleteDirectory($dir);
            }
        }
        $trace = $this->tracePath($recording);
        if (is_file($trace)) {
            File::delete($trace);
        }
    }

    /**
     * Sanitise a user supplied filename: basename only, no traversal, no control chars.
     */
    public function safeFilename(string $name): string
    {
        $name = str_replace('\\', '/', $name);
        $name = basename($name);
        $name = preg_replace('/[\x00-\x1F\x7F]/', '', $name) ?? '';
        $name = trim($name, ". \t");
        if ($name === '' || $name === '.' || $name === '..') {
            throw new InvalidArgumentException('Invalid filename.');
        }

        return $name;
    }

    public function sha256(string $path): string
    {
        return hash_file('sha256', $path) ?: '';
    }

    /**
     * Guarantees the resolved path stays under the data directory (rejects "..", absolute escapes, etc.).
     */
    public function safe(string $path): string
    {
        $normalized = $this->normalize($path);
        $root = $this->dataDir();
        $parts = explode('/', $normalized);
        if (in_array('..', $parts, true)) {
            throw new InvalidArgumentException('Path traversal is not allowed.');
        }
        if (! str_starts_with($normalized.'/', $root.'/')) {
            throw new InvalidArgumentException('Path is outside the data directory.');
        }

        return $normalized;
    }

    public function normalize(string $path): string
    {
        $path = str_replace('\\', '/', $path);
        $path = preg_replace('#/+#', '/', $path) ?? $path;

        return rtrim($path, '/') ?: '/';
    }
}
