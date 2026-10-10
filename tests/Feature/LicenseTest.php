<?php

namespace Tests\Feature;

use Illuminate\Http\UploadedFile;
use Tests\TestCase;

class LicenseTest extends TestCase
{
    public function test_status_is_proxied_from_the_engine(): void
    {
        $this->getJson('/api/license')->assertOk()
            ->assertJsonPath('state', 'trial')
            ->assertJsonPath('allowed', true)
            ->assertJsonPath('trial_info.days_left', 9)
            ->assertJsonPath('machine_id', 'K3J9Q-7ZP2M-ABCDE-23456');
    }

    public function test_app_status_carries_a_license_summary(): void
    {
        $this->getJson('/api/app/status')->assertOk()
            ->assertJsonPath('license.state', 'trial')
            ->assertJsonPath('license.allowed', true);
        $this->engine->down = true;
        $this->getJson('/api/app/status')->assertOk()->assertJsonPath('license', null);
    }

    public function test_installing_a_signed_license_activates_and_a_bad_file_is_refused(): void
    {
        $this->engine->licenseState = 'unlicensed';
        $bad = UploadedFile::fake()->createWithContent('x.qlicense', '{"license": {"product": "HVSR Studio"}}');
        $this->post('/api/license', ['file' => $bad], ['Accept' => 'application/json'])
            ->assertStatus(422)->assertJsonPath('message', 'This is not a valid HVSR Studio licence file.');

        $good = UploadedFile::fake()->createWithContent('Acme-HVSR-2026-0001.qlicense', '{"license": {"product": "HVSR Studio"}, "signature": "abc"}');
        $this->post('/api/license', ['file' => $good], ['Accept' => 'application/json'])
            ->assertOk()->assertJsonPath('state', 'licensed')->assertJsonPath('license.customer', 'Test Geo Ltd');
        $this->assertSame([], glob(storage_path('app/license-staging/*')) ?: []);
        $this->assertSame('licensed', $this->engine->licenseState);
    }

    public function test_wrong_extension_is_rejected_before_reaching_the_engine(): void
    {
        $file = UploadedFile::fake()->createWithContent('photo.png', 'x');
        $this->post('/api/license', ['file' => $file], ['Accept' => 'application/json'])->assertStatus(422);
        $this->assertNull(collect($this->engine->calls)->firstWhere('method', 'installLicense'));
    }

    public function test_locked_calculations_answer_402_with_the_license_flag(): void
    {
        $project = $this->createProject();
        $recording = $this->importRecording($project['id']);
        $this->engine->licenseState = 'unlicensed';

        $response = $this->postJson("/api/recordings/{$recording['id']}/analyses", [
            'name' => 'locked', 'params' => ['window_length_s' => 60, 'overlap' => 0.5],
        ]);
        $response->assertStatus(402)->assertJsonPath('license_required', true);
        $this->assertStringContainsString('open, view and save', $response->json('message'));
        $this->postJson("/api/recordings/{$recording['id']}/spectra", ['kind' => 'fas'])->assertStatus(402);
        // Data stays readable without a licence.
        $this->getJson("/api/recordings/{$recording['id']}")->assertOk();
    }

    public function test_eula_is_listed_among_the_bundled_documents(): void
    {
        $this->getJson('/api/docs')->assertOk()->assertJsonFragment(['key' => 'eula', 'title' => 'Licence agreement']);
    }
}
