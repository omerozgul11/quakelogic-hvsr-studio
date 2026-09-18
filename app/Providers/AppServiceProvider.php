<?php

namespace App\Providers;

use App\Services\Engine\EngineClient;
use App\Services\Engine\EngineClientInterface;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(EngineClientInterface::class, fn () => EngineClient::fromConfig());
    }

    public function boot(): void
    {
        //
    }
}
