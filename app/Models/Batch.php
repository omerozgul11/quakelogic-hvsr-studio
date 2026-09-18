<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Batch extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = ['run_steps' => 'bool', 'current_index' => 'int'];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }

    public function preset(): BelongsTo
    {
        return $this->belongsTo(ProcessingPreset::class, 'preset_id');
    }

    public function items(): HasMany
    {
        return $this->hasMany(BatchItem::class)->orderBy('position');
    }
}
