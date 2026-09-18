<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class RecordingFile extends Model
{
    protected $guarded = [];

    protected $casts = ['size_bytes' => 'int'];

    public function recording(): BelongsTo
    {
        return $this->belongsTo(Recording::class);
    }
}
