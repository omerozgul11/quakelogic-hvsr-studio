<?php

namespace Tests\Unit;

use App\Services\Projects\ProjectStorage;
use InvalidArgumentException;
use Tests\TestCase;

class ProjectStorageTest extends TestCase
{
    public function test_safe_rejects_traversal_and_outside_paths(): void
    {
        $storage = new ProjectStorage;
        $this->assertSame($this->dataDir.'/projects/x', $storage->safe($this->dataDir.'/projects//x/'));

        $this->expectException(InvalidArgumentException::class);
        $storage->safe($this->dataDir.'/projects/../../etc/passwd');
    }

    public function test_safe_rejects_paths_outside_data_dir(): void
    {
        $this->expectException(InvalidArgumentException::class);
        (new ProjectStorage)->safe('/etc/passwd');
    }

    public function test_safe_filename(): void
    {
        $storage = new ProjectStorage;
        $this->assertSame('passwd', $storage->safeFilename('../../etc/passwd'));
        $this->assertSame('site A.csv', $storage->safeFilename('C:\\data\\site A.csv'));
        $this->expectException(InvalidArgumentException::class);
        $storage->safeFilename('..');
    }

    public function test_upload_with_traversal_name_is_stored_safely(): void
    {
        $project = $this->createProject();
        $uploads = $this->uploadFiles($project['id'], ['../../evil.csv']);
        $this->assertSame('evil.csv', $uploads[0]['name']);
        $this->assertFileDoesNotExist($this->dataDir.'/evil.csv');
    }
}
