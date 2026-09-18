<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Response;

/**
 * Serves the bundled documentation (Markdown) to the in-app manual. Fully offline.
 */
class DocsController extends Controller
{
    /** @var array<string, array{path: string, title: string}> */
    public const DOCS = [
        'user-guide' => ['path' => 'docs/user-guide.md', 'title' => 'User guide'],
        'hvsr-algorithms' => ['path' => 'docs/hvsr-algorithms.md', 'title' => 'HVSR algorithms'],
        'validation' => ['path' => 'docs/validation.md', 'title' => 'Numerical validation'],
        'notices' => ['path' => 'THIRD_PARTY_NOTICES.md', 'title' => 'Third-party notices'],
    ];

    public function index(): array
    {
        return collect(self::DOCS)
            ->map(fn (array $doc, string $key) => ['key' => $key, 'title' => $doc['title'], 'available' => is_file(base_path($doc['path']))])
            ->values()
            ->all();
    }

    public function show(string $doc): Response
    {
        abort_unless(isset(self::DOCS[$doc]), 404, 'Unknown document.');
        $path = base_path(self::DOCS[$doc]['path']);
        abort_unless(is_file($path), 404, 'This document is not included in the installation.');

        return response(file_get_contents($path), 200, ['Content-Type' => 'text/markdown; charset=utf-8']);
    }
}
