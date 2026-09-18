<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('projects', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->string('name');
            $table->string('slug')->unique();
            $table->text('description')->nullable();
            $table->string('folder');
            $table->json('settings')->nullable();
            $table->timestamps();
        });

        Schema::create('stations', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->string('code');
            $table->string('name')->nullable();
            $table->decimal('latitude', 10, 6)->nullable();
            $table->decimal('longitude', 10, 6)->nullable();
            $table->decimal('elevation', 10, 2)->nullable();
            $table->decimal('orientation_deg', 7, 2)->nullable();
            $table->text('notes')->nullable();
            $table->timestamps();
        });

        Schema::create('recordings', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->foreignId('station_id')->nullable()->constrained()->nullOnDelete();
            $table->string('name');
            $table->string('status', 20)->default('pending');
            $table->string('format', 20)->nullable();
            $table->double('sample_rate')->nullable();
            $table->string('start_time')->nullable();
            $table->double('duration_s')->nullable();
            $table->unsignedBigInteger('n_samples')->nullable();
            $table->string('units')->nullable();
            $table->string('unit_kind')->nullable();
            $table->json('import_settings')->nullable();
            $table->json('validation')->nullable();
            $table->string('canonical_path')->nullable();
            $table->json('meta')->nullable();
            $table->boolean('is_synthetic')->default(false);
            $table->text('notes')->nullable();
            $table->timestamps();
        });

        Schema::create('recording_files', function (Blueprint $table) {
            $table->id();
            $table->foreignId('recording_id')->constrained()->cascadeOnDelete();
            $table->string('original_name');
            $table->string('stored_path');
            $table->unsignedBigInteger('size_bytes')->default(0);
            $table->string('sha256', 64)->nullable();
            $table->string('role', 10)->default('all');
            $table->timestamps();
        });

        Schema::create('uploads', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->string('original_name');
            $table->string('stored_path');
            $table->unsignedBigInteger('size_bytes')->default(0);
            $table->string('sha256', 64)->nullable();
            $table->json('inspect')->nullable();
            $table->boolean('consumed')->default(false);
            $table->timestamps();
        });

        Schema::create('processing_presets', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->nullable()->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->text('description')->nullable();
            $table->json('steps')->nullable();
            $table->json('hvsr_params')->nullable();
            $table->timestamps();
        });

        Schema::create('processing_runs', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->foreignId('recording_id')->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->json('steps')->nullable();
            $table->json('applied')->nullable();
            $table->json('warnings')->nullable();
            $table->string('status', 20)->default('queued');
            $table->string('job_id')->nullable();
            $table->double('progress')->default(0);
            $table->text('error')->nullable();
            $table->string('output_path')->nullable();
            $table->json('meta')->nullable();
            $table->string('engine_version')->nullable();
            $table->timestamps();
        });

        Schema::create('analyses', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->foreignId('recording_id')->constrained()->cascadeOnDelete();
            $table->foreignId('processing_run_id')->nullable()->constrained('processing_runs')->nullOnDelete();
            $table->string('name');
            $table->json('params')->nullable();
            $table->json('window_overrides')->nullable();
            $table->json('manual_peak')->nullable();
            $table->unsignedBigInteger('random_seed')->nullable();
            $table->string('status', 20)->default('queued');
            $table->string('job_id')->nullable();
            $table->double('progress')->default(0);
            $table->text('error')->nullable();
            $table->string('result_dir')->nullable();
            $table->json('summary')->nullable();
            $table->string('engine_version')->nullable();
            $table->string('report_path')->nullable();
            $table->string('report_job_id')->nullable();
            $table->string('report_status', 20)->nullable();
            $table->timestamps();
        });

        Schema::create('batches', function (Blueprint $table) {
            $table->id();
            $table->string('ulid', 26)->unique();
            $table->foreignId('project_id')->constrained()->cascadeOnDelete();
            $table->string('name');
            $table->foreignId('preset_id')->nullable()->constrained('processing_presets')->nullOnDelete();
            $table->boolean('run_steps')->default(true);
            $table->string('status', 20)->default('queued');
            $table->unsignedInteger('current_index')->default(0);
            $table->timestamps();
        });

        Schema::create('batch_items', function (Blueprint $table) {
            $table->id();
            $table->foreignId('batch_id')->constrained()->cascadeOnDelete();
            $table->foreignId('recording_id')->constrained()->cascadeOnDelete();
            $table->foreignId('processing_run_id')->nullable()->constrained('processing_runs')->nullOnDelete();
            $table->foreignId('analysis_id')->nullable()->constrained('analyses')->nullOnDelete();
            $table->unsignedInteger('position')->default(0);
            $table->string('status', 20)->default('queued');
            $table->text('error')->nullable();
            $table->timestamps();
        });

        Schema::create('activity_log', function (Blueprint $table) {
            $table->id();
            $table->foreignId('project_id')->nullable()->constrained()->cascadeOnDelete();
            $table->string('subject_type')->nullable();
            $table->string('subject_id')->nullable();
            $table->string('action');
            $table->json('details')->nullable();
            $table->timestamp('created_at')->useCurrent();
        });

        Schema::create('settings', function (Blueprint $table) {
            $table->id();
            $table->string('key')->unique();
            $table->json('value')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        foreach (['settings', 'activity_log', 'batch_items', 'batches', 'analyses', 'processing_runs', 'processing_presets', 'uploads', 'recording_files', 'recordings', 'stations', 'projects'] as $t) {
            Schema::dropIfExists($t);
        }
    }
};
