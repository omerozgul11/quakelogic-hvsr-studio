<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('analyses', function (Blueprint $table) {
            if (! Schema::hasColumn('analyses', 'survey')) {
                $table->json('survey')->nullable();
            }
            if (! Schema::hasColumn('analyses', 'models')) {
                $table->json('models')->nullable();
            }
        });
    }

    public function down(): void
    {
        Schema::table('analyses', function (Blueprint $table) {
            foreach (['survey', 'models'] as $col) {
                if (Schema::hasColumn('analyses', $col)) {
                    $table->dropColumn($col);
                }
            }
        });
    }
};
