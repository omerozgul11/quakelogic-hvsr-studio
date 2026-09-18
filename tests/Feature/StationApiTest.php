<?php

namespace Tests\Feature;

use Tests\TestCase;

class StationApiTest extends TestCase
{
    public function test_station_crud(): void
    {
        $project = $this->createProject();
        $station = $this->postJson("/api/projects/{$project['id']}/stations", [
            'code' => 'STA1', 'name' => 'Station one', 'latitude' => 40.1, 'longitude' => -105.2, 'orientation_deg' => 12.5,
        ])->assertCreated()->json();
        $this->assertSame('STA1', $station['code']);
        $this->assertSame(12.5, $station['orientation_deg']);

        $this->putJson("/api/stations/{$station['id']}", ['name' => 'Renamed'])->assertOk()->assertJsonPath('name', 'Renamed');
        $this->postJson("/api/projects/{$project['id']}/stations", ['code' => 'X', 'latitude' => 123])->assertStatus(422);

        $this->getJson("/api/projects/{$project['id']}")->assertJsonCount(1, 'stations');
        $this->deleteJson("/api/stations/{$station['id']}")->assertOk();
        $this->getJson("/api/projects/{$project['id']}")->assertJsonCount(0, 'stations');
    }
}
