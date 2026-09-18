<?php

use Illuminate\Support\Facades\Route;

Route::get('/THIRD_PARTY_NOTICES.md', function () {
    $path = base_path('THIRD_PARTY_NOTICES.md');
    abort_unless(is_file($path), 404);

    return response()->file($path, ['Content-Type' => 'text/plain; charset=utf-8']);
});

Route::get('/{any?}', fn () => view('app'))->where('any', '^(?!api(/|$)).*$');
