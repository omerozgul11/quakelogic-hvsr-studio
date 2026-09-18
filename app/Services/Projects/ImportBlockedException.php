<?php

namespace App\Services\Projects;

use RuntimeException;

class ImportBlockedException extends RuntimeException
{
    public function __construct(public readonly array $validation)
    {
        parent::__construct('Import blocked by validation errors.');
    }
}
