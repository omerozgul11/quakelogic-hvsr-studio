<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ProcessingRun extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = [
        'steps' => 'array',
        'applied' => 'array',
        'warnings' => 'array',
        'meta' => 'array',
        'progress' => 'float',
    ];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }

    public function recording(): BelongsTo
    {
        return $this->belongsTo(Recording::class);
    }

    public function analyses(): HasMany
    {
        return $this->hasMany(Analysis::class, 'processing_run_id');
    }

    public function isActive(): bool
    {
        return in_array($this->status, ['queued', 'running'], true);
    }
}
