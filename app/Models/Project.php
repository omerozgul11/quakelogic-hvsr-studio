<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Project extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = ['settings' => 'array'];

    public function stations(): HasMany
    {
        return $this->hasMany(Station::class);
    }

    public function recordings(): HasMany
    {
        return $this->hasMany(Recording::class);
    }

    public function presets(): HasMany
    {
        return $this->hasMany(ProcessingPreset::class);
    }

    public function runs(): HasMany
    {
        return $this->hasMany(ProcessingRun::class);
    }

    public function analyses(): HasMany
    {
        return $this->hasMany(Analysis::class);
    }

    public function batches(): HasMany
    {
        return $this->hasMany(Batch::class);
    }

    public function uploads(): HasMany
    {
        return $this->hasMany(Upload::class);
    }

    public function activity(): HasMany
    {
        return $this->hasMany(ActivityLog::class);
    }
}
