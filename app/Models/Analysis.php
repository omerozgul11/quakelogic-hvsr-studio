<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Analysis extends Model
{
    use HasUlid;

    protected $table = 'analyses';

    protected $guarded = [];

    protected $casts = [
        'params' => 'array',
        'window_overrides' => 'array',
        'manual_peak' => 'array',
        'summary' => 'array',
        'survey' => 'array',
        'models' => 'array',
        'progress' => 'float',
        'random_seed' => 'int',
    ];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }

    public function recording(): BelongsTo
    {
        return $this->belongsTo(Recording::class);
    }

    public function run(): BelongsTo
    {
        return $this->belongsTo(ProcessingRun::class, 'processing_run_id');
    }

    public function isActive(): bool
    {
        return in_array($this->status, ['queued', 'running'], true);
    }
}
