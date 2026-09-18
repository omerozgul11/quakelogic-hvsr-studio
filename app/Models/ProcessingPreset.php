<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ProcessingPreset extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = ['steps' => 'array', 'hvsr_params' => 'array'];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }
}
