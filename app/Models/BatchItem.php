<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BatchItem extends Model
{
    protected $guarded = [];

    protected $casts = ['position' => 'int'];

    public function batch(): BelongsTo
    {
        return $this->belongsTo(Batch::class);
    }

    public function recording(): BelongsTo
    {
        return $this->belongsTo(Recording::class);
    }

    public function run(): BelongsTo
    {
        return $this->belongsTo(ProcessingRun::class, 'processing_run_id');
    }

    public function analysis(): BelongsTo
    {
        return $this->belongsTo(Analysis::class);
    }
}
