<?php

namespace App\Console\Commands;

use App\Services\Engine\EngineClientInterface;
use App\Services\Projects\ProjectStorage;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Throwable;

class DoctorCommand extends Command
{
    protected $signature = 'hvsr:doctor';

    protected $description = 'Check the local installation: data directory, SQLite database, processing engine';

    public function handle(ProjectStorage $storage, EngineClientInterface $engine): int
    {
        $rows = [];
        $ok = true;

        $dataDir = $storage->dataDir();
        $writable = is_dir($dataDir) && is_writable($dataDir);
        $rows[] = ['Data directory', $writable ? 'OK' : 'FAIL', $dataDir.($writable ? '' : ' (missing or not writable — run php artisan hvsr:setup)')];
        $ok = $ok && $writable;

        try {
            DB::connection()->getPdo();
            $migrated = Schema::hasTable('projects');
            $rows[] = ['SQLite database', $migrated ? 'OK' : 'FAIL', config('database.connections.sqlite.database').($migrated ? '' : ' (tables missing — run php artisan hvsr:setup)')];
            $ok = $ok && $migrated;
        } catch (Throwable $e) {
            $rows[] = ['SQLite database', 'FAIL', $e->getMessage()];
            $ok = false;
        }

        try {
            $health = $engine->health();
            $rows[] = ['Processing engine', ($health['status'] ?? '') === 'ok' ? 'OK' : 'WARN', config('hvsr.engine_url').' — engine '.($health['engine_version'] ?? '?').', Python '.($health['python'] ?? '?')];
        } catch (Throwable $e) {
            $rows[] = ['Processing engine', 'DOWN', config('hvsr.engine_url').' — '.$e->getMessage()];
            $ok = false;
        }

        foreach (['pdo_sqlite', 'mbstring', 'fileinfo', 'openssl', 'curl'] as $ext) {
            $loaded = extension_loaded($ext);
            $rows[] = ['PHP extension '.$ext, $loaded ? 'OK' : 'FAIL', PHP_VERSION];
            $ok = $ok && $loaded;
        }

        $this->table(['Check', 'Status', 'Detail'], $rows);
        $this->line($ok ? '<info>All checks passed.</info>' : '<comment>Some checks failed.</comment>');

        return $ok ? self::SUCCESS : self::FAILURE;
    }
}
