<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreStationRequest;
use App\Http\Requests\UpdateStationRequest;
use App\Http\Serializers\Json;
use App\Models\ActivityLog;
use App\Models\Project;
use App\Models\Station;
use Illuminate\Http\JsonResponse;

class StationController extends Controller
{
    public function store(StoreStationRequest $request, Project $project): JsonResponse
    {
        $station = $project->stations()->create($request->validated());
        ActivityLog::record($project->id, 'station.created', $station, ['code' => $station->code]);

        return response()->json(Json::station($station), 201);
    }

    public function update(UpdateStationRequest $request, Station $station): JsonResponse
    {
        $station->update($request->validated());
        ActivityLog::record($station->project_id, 'station.updated', $station, $request->validated());

        return response()->json(Json::station($station));
    }

    public function destroy(Station $station): JsonResponse
    {
        ActivityLog::record($station->project_id, 'station.deleted', $station, ['code' => $station->code]);
        $station->delete();

        return response()->json(['deleted' => true]);
    }
}
