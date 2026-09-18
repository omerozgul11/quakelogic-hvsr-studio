<?php

namespace App\Console\Commands;

use App\Services\Projects\ProjectStorage;
use Database\Seeders\PresetSeeder;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\File;

class SetupCommand extends Command
{
    protected $signature = 'hvsr:setup {--quiet-migrations : Hide migration output}';

    protected $description = 'Create the data directory, run migrations and seed the built-in processing presets';

    public function handle(ProjectStorage $storage): int
    {
        $dataDir = $storage->dataDir();
        File::ensureDirectoryExists($dataDir);
        $storage->ensureDataDir();
        $this->info('Data directory: '.$dataDir);

        $db = config('database.connections.sqlite.database');
        if ($db !== ':memory:') {
            File::ensureDirectoryExists(dirname($db));
            if (! file_exists($db)) {
                touch($db);
                $this->info('Created database: '.$db);
            }
        }

        foreach (['framework/cache/data', 'framework/sessions', 'framework/views', 'logs'] as $dir) {
            File::ensureDirectoryExists(storage_path($dir));
        }

        Artisan::call('migrate', ['--force' => true]);
        if (! $this->option('quiet-migrations')) {
            $this->line(trim(Artisan::output()));
        }

        Artisan::call('db:seed', ['--class' => PresetSeeder::class, '--force' => true]);
        $this->info('Built-in presets: '.count(PresetSeeder::builtin()).' ensured.');
        $this->info('Setup complete.');

        return self::SUCCESS;
    }
}
