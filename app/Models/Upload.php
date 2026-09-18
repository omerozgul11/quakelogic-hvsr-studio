<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Upload extends Model
{
    use HasUlid;

    protected $guarded = [];

    protected $casts = ['inspect' => 'array', 'consumed' => 'bool', 'size_bytes' => 'int'];

    public function project(): BelongsTo
    {
        return $this->belongsTo(Project::class);
    }
}
