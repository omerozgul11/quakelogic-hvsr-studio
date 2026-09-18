<?php

namespace App\Http\Serializers;

use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Models\Batch;
use App\Models\BatchItem;
use App\Models\ProcessingPreset;
use App\Models\ProcessingRun;
use App\Models\Project;
use App\Models\Recording;
use App\Models\Station;
use App\Models\Upload;

/**
 * Plain-array JSON shapes for the SPA. ULIDs are exposed as `id`.
 */
class Json
{
    public static function project(Project $p, bool $full = false): array
    {
        $out = [
            'id' => $p->ulid,
            'name' => $p->name,
            'slug' => $p->slug,
            'description' => $p->description,
            'folder' => $p->folder,
            'settings' => $p->settings ?? (object) [],
            'created_at' => $p->created_at?->toIso8601String(),
            'updated_at' => $p->updated_at?->toIso8601String(),
            'counts' => [
                'stations' => $p->stations()->count(),
                'recordings' => $p->recordings()->count(),
                'analyses' => $p->analyses()->count(),
            ],
        ];
        if ($full) {
            $out['stations'] = $p->stations->map(fn ($s) => self::station($s))->values()->all();
            $out['recordings'] = $p->recordings->map(fn ($r) => self::recording($r, true))->values()->all();
            $out['presets'] = ProcessingPreset::query()->where(fn ($q) => $q->whereNull('project_id')->orWhere('project_id', $p->id))
                ->orderBy('name')->get()->map(fn ($x) => self::preset($x))->values()->all();
            $out['batches'] = $p->batches()->with('items')->latest()->get()->map(fn ($b) => self::batch($b))->values()->all();
        }

        return $out;
    }

    public static function station(Station $s): array
    {
        return [
            'id' => $s->ulid,
            'project_id' => $s->project->ulid,
            'code' => $s->code,
            'name' => $s->name,
            'latitude' => $s->latitude,
            'longitude' => $s->longitude,
            'elevation' => $s->elevation,
            'orientation_deg' => $s->orientation_deg,
            'notes' => $s->notes,
            'created_at' => $s->created_at?->toIso8601String(),
            'updated_at' => $s->updated_at?->toIso8601String(),
        ];
    }

    public static function recording(Recording $r, bool $withChildren = false): array
    {
        $out = [
            'id' => $r->ulid,
            'project_id' => $r->project->ulid,
            'station_id' => $r->station?->ulid,
            'station' => $r->station ? ['id' => $r->station->ulid, 'code' => $r->station->code, 'name' => $r->station->name] : null,
            'name' => $r->name,
            'status' => $r->status,
            'format' => $r->format,
            'sample_rate' => $r->sample_rate,
            'start_time' => $r->start_time,
            'duration_s' => $r->duration_s,
            'n_samples' => $r->n_samples,
            'units' => $r->units,
            'unit_kind' => $r->unit_kind,
            'is_synthetic' => $r->is_synthetic,
            'import_settings' => $r->import_settings,
            'validation' => $r->validation,
            'meta' => $r->meta,
            'notes' => $r->notes,
            'files' => $r->files->map(fn ($f) => [
                'id' => $f->id, 'name' => $f->original_name, 'role' => $f->role, 'size_bytes' => $f->size_bytes, 'sha256' => $f->sha256,
            ])->values()->all(),
            'created_at' => $r->created_at?->toIso8601String(),
            'updated_at' => $r->updated_at?->toIso8601String(),
        ];
        if ($withChildren) {
            $out['runs'] = $r->runs()->orderBy('id')->get()->map(fn ($x) => self::run($x))->values()->all();
            $out['analyses'] = $r->analyses()->orderBy('id')->get()->map(fn ($x) => self::analysis($x))->values()->all();
        }

        return $out;
    }

    public static function upload(Upload $u): array
    {
        return [
            'upload_id' => $u->ulid,
            'name' => $u->original_name,
            'size' => $u->size_bytes,
            'sha256' => $u->sha256,
            'inspect' => $u->inspect,
        ];
    }

    public static function preset(ProcessingPreset $p): array
    {
        return [
            'id' => $p->ulid,
            'project_id' => $p->project?->ulid,
            'builtin' => $p->project_id === null,
            'name' => $p->name,
            'description' => $p->description,
            'steps' => $p->steps ?? [],
            'hvsr_params' => $p->hvsr_params ?? (object) [],
            'created_at' => $p->created_at?->toIso8601String(),
            'updated_at' => $p->updated_at?->toIso8601String(),
        ];
    }

    public static function run(ProcessingRun $r, ?array $job = null): array
    {
        return [
            'id' => $r->ulid,
            'project_id' => $r->project->ulid,
            'recording_id' => $r->recording->ulid,
            'name' => $r->name,
            'steps' => $r->steps ?? [],
            'applied' => $r->applied,
            'warnings' => $r->warnings ?? [],
            'status' => $r->status,
            'job_id' => $r->job_id,
            'progress' => $r->progress,
            'error' => $r->error,
            'output_path' => $r->output_path,
            'meta' => $r->meta,
            'engine_version' => $r->engine_version,
            'job' => $job,
            'created_at' => $r->created_at?->toIso8601String(),
            'updated_at' => $r->updated_at?->toIso8601String(),
        ];
    }

    /**
     * The engine summary block plus flat convenience fields used by lists and tables.
     */
    public static function summary(?array $summary): ?array
    {
        if ($summary === null) {
            return null;
        }
        $selected = $summary['peaks']['selected'] ?? null;

        return $summary + [
            'f0' => $selected['frequency'] ?? null,
            'a0' => $selected['amplitude'] ?? null,
            'peak_status' => $summary['peaks']['status'] ?? null,
            'peak_source' => $selected['source'] ?? null,
            'count_accepted' => $summary['windows']['count_accepted'] ?? null,
            'count_total' => $summary['windows']['count_total'] ?? null,
            'sesame_reliability' => $summary['sesame']['reliability_passed'] ?? null,
            'sesame_clarity_count' => $summary['sesame']['clarity_passed_count'] ?? null,
        ];
    }

    public static function analysis(Analysis $a, ?array $result = null, ?array $job = null): array
    {
        return [
            'id' => $a->ulid,
            'project_id' => $a->project->ulid,
            'recording_id' => $a->recording->ulid,
            'recording_name' => $a->recording->name,
            'station_code' => $a->recording->station?->code,
            'run_id' => $a->run?->ulid,
            'processing_run_id' => $a->run?->ulid,
            'run_name' => $a->run?->name,
            'name' => $a->name,
            'params' => $a->params ?? (object) [],
            'window_overrides' => $a->window_overrides ?? (object) [],
            'manual_peak' => $a->manual_peak,
            'random_seed' => $a->random_seed,
            'status' => $a->status,
            'job_id' => $a->job_id,
            'progress' => $a->progress,
            'error' => $a->error,
            'result_dir' => $a->result_dir,
            'summary' => self::summary($a->summary),
            'engine_version' => $a->engine_version,
            'report_status' => $a->report_status,
            'report_ready' => $a->report_status === 'done' && $a->report_path && is_file($a->report_path),
            'survey' => $a->survey,
            'models' => $a->models ?? [],
            'result' => $result,
            'job' => $job,
            'created_at' => $a->created_at?->toIso8601String(),
            'updated_at' => $a->updated_at?->toIso8601String(),
        ];
    }

    public static function batch(Batch $b): array
    {
        $items = $b->items->map(fn (BatchItem $i) => [
            'id' => $i->id,
            'position' => $i->position,
            'recording_id' => $i->recording?->ulid,
            'recording_name' => $i->recording?->name,
            'run_id' => $i->run?->ulid,
            'analysis_id' => $i->analysis?->ulid,
            'status' => $i->status,
            'error' => $i->error,
            'progress' => $i->analysis?->progress ?? $i->run?->progress ?? 0,
            'summary' => self::summary($i->analysis?->summary),
        ])->values()->all();

        $counts = ['total' => count($items)];
        foreach (['queued', 'running', 'done', 'failed', 'skipped', 'cancelled'] as $s) {
            $counts[$s] = count(array_filter($items, fn ($i) => $i['status'] === $s));
        }

        return [
            'id' => $b->ulid,
            'project_id' => $b->project->ulid,
            'name' => $b->name,
            'preset_id' => $b->preset?->ulid,
            'preset_name' => $b->preset?->name,
            'run_steps' => $b->run_steps,
            'status' => $b->status,
            'current_index' => $b->current_index,
            'counts' => $counts,
            'items' => $items,
            'created_at' => $b->created_at?->toIso8601String(),
            'updated_at' => $b->updated_at?->toIso8601String(),
        ];
    }

    public static function activity(ActivityLog $l): array
    {
        return [
            'id' => $l->id,
            'action' => $l->action,
            'subject_type' => $l->subject_type,
            'subject_id' => $l->subject_id,
            'details' => $l->details,
            'created_at' => $l->created_at?->toIso8601String(),
        ];
    }
}
