<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Recording extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = [
        'import_settings' => 'array',
        'validation' => 'array',
        'meta' => 'array',
        'is_synthetic' => 'bool',
        'sample_rate' => 'float',
        'duration_s' => 'float',
        'n_samples' => 'int',
    ];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }

    public function station(): BelongsTo
    {
        return $this->belongsTo(Station::class);
    }

    public function files(): HasMany
    {
        return $this->hasMany(RecordingFile::class);
    }

    public function runs(): HasMany
    {
        return $this->hasMany(ProcessingRun::class);
    }

    public function analyses(): HasMany
    {
        return $this->hasMany(Analysis::class);
    }
}
