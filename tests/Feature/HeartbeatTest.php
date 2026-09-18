<?php

namespace Tests\Feature;

use Tests\TestCase;

class HeartbeatTest extends TestCase
{
    public function test_heartbeat_is_reported_in_the_status(): void
    {
        $this->getJson('/api/app/status')->assertOk()->assertJsonPath('heartbeat_age_s', null);
        $this->postJson('/api/app/heartbeat')->assertOk()->assertJson(['ok' => true]);
        $age = $this->getJson('/api/app/status')->assertOk()->json('heartbeat_age_s');
        $this->assertIsNumeric($age);
        $this->assertLessThan(5, $age);
    }

    public function test_goodbye_is_reported_until_the_next_heartbeat(): void
    {
        $this->postJson('/api/app/goodbye')->assertOk();
        $this->assertNotNull($this->getJson('/api/app/status')->json('goodbye_age_s'));
        $this->postJson('/api/app/heartbeat')->assertOk();
        $this->assertNull($this->getJson('/api/app/status')->json('goodbye_age_s'));
    }
}
