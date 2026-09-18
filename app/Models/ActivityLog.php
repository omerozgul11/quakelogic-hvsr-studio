<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ActivityLog extends Model
{
    public $timestamps = false;

    protected $table = 'activity_log';

    protected $guarded = [];

    protected $casts = ['details' => 'array', 'created_at' => 'datetime'];

    public static function record(?int $projectId, string $action, ?Model $subject = null, array $details = []): self
    {
        return static::create([
            'project_id' => $projectId,
            'subject_type' => $subject ? class_basename($subject) : null,
            'subject_id' => $subject?->ulid ?? $subject?->getKey(),
            'action' => $action,
            'details' => $details,
            'created_at' => now(),
        ]);
    }
}
