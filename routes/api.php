<?php

use App\Http\Controllers\Api\AnalysisController;
use App\Http\Controllers\Api\AppStatusController;
use App\Http\Controllers\Api\BatchController;
use App\Http\Controllers\Api\CompareController;
use App\Http\Controllers\Api\CurveController;
use App\Http\Controllers\Api\DocsController;
use App\Http\Controllers\Api\EngineController;
use App\Http\Controllers\Api\PresetController;
use App\Http\Controllers\Api\ProjectController;
use App\Http\Controllers\Api\RecordingController;
use App\Http\Controllers\Api\RunController;
use App\Http\Controllers\Api\StationController;
use App\Http\Controllers\Api\SurveyController;
use App\Http\Controllers\Api\UploadController;
use Illuminate\Support\Facades\Route;

Route::get('/app/status', [AppStatusController::class, 'status']);
Route::get('/settings', [AppStatusController::class, 'settings']);
Route::put('/settings', [AppStatusController::class, 'updateSettings']);

Route::get('/projects', [ProjectController::class, 'index']);
Route::post('/projects', [ProjectController::class, 'store']);
Route::get('/projects/{project}', [ProjectController::class, 'show']);
Route::put('/projects/{project}', [ProjectController::class, 'update']);
Route::delete('/projects/{project}', [ProjectController::class, 'destroy']);
Route::get('/projects/{project}/history', [ProjectController::class, 'history']);
Route::get('/projects/{project}/backup', [ProjectController::class, 'backup']);
Route::post('/projects/restore', [ProjectController::class, 'restore']);
Route::post('/projects/{project}/curves', [CurveController::class, 'store']);

Route::post('/projects/{project}/stations', [StationController::class, 'store']);
Route::put('/stations/{station}', [StationController::class, 'update']);
Route::delete('/stations/{station}', [StationController::class, 'destroy']);

Route::post('/projects/{project}/uploads', [UploadController::class, 'store']);

Route::post('/projects/{project}/recordings', [RecordingController::class, 'store']);
Route::get('/recordings/{recording}', [RecordingController::class, 'show']);
Route::put('/recordings/{recording}', [RecordingController::class, 'update']);
Route::delete('/recordings/{recording}', [RecordingController::class, 'destroy']);
Route::get('/recordings/{recording}/data', [RecordingController::class, 'data']);
Route::post('/recordings/{recording}/spectra', [RecordingController::class, 'spectra']);
Route::post('/recordings/{recording}/processing/preview', [RecordingController::class, 'preview']);
Route::post('/recordings/{recording}/windows', [RecordingController::class, 'windows']);
Route::post('/recordings/{recording}/windows/import', [RecordingController::class, 'importWindows']);
Route::get('/recordings/{recording}/samples', [RecordingController::class, 'samples']);

Route::post('/recordings/{recording}/runs', [RunController::class, 'store']);
Route::get('/runs/{run}', [RunController::class, 'show']);
Route::delete('/runs/{run}', [RunController::class, 'destroy']);

Route::post('/engine/filter-response', [EngineController::class, 'filterResponse']);
Route::post('/engine/model-hvsr', [EngineController::class, 'modelHvsr']);
Route::get('/jobs/{job}', [EngineController::class, 'job']);
Route::post('/jobs/{job}/cancel', [EngineController::class, 'cancelJob']);

Route::get('/projects/{project}/presets', [PresetController::class, 'index']);
Route::post('/projects/{project}/presets', [PresetController::class, 'store']);
Route::put('/presets/{preset}', [PresetController::class, 'update']);
Route::delete('/presets/{preset}', [PresetController::class, 'destroy']);

Route::post('/recordings/{recording}/analyses', [AnalysisController::class, 'store']);
Route::get('/analyses/{analysis}', [AnalysisController::class, 'show']);
Route::put('/analyses/{analysis}', [AnalysisController::class, 'update']);
Route::delete('/analyses/{analysis}', [AnalysisController::class, 'destroy']);
Route::post('/analyses/{analysis}/cancel', [AnalysisController::class, 'cancel']);
Route::get('/analyses/{analysis}/window-curves', [AnalysisController::class, 'windowCurves']);
Route::post('/analyses/{analysis}/rerun', [AnalysisController::class, 'rerun']);
Route::post('/analyses/{analysis}/select-peak', [AnalysisController::class, 'selectPeak']);
Route::get('/analyses/{analysis}/exports/{kind}', [AnalysisController::class, 'export']);
Route::get('/analyses/{analysis}/figure', [AnalysisController::class, 'figure']);
Route::post('/analyses/{analysis}/report', [AnalysisController::class, 'createReport']);
Route::get('/analyses/{analysis}/report', [AnalysisController::class, 'report']);
Route::get('/analyses/{analysis}/survey', [SurveyController::class, 'show']);
Route::put('/analyses/{analysis}/survey', [SurveyController::class, 'update']);
Route::post('/analyses/{analysis}/survey', [SurveyController::class, 'update']);
Route::get('/analyses/{analysis}/survey/photo/{index}', [SurveyController::class, 'photo'])->where('index', '[12]');
Route::put('/analyses/{analysis}/models', [AnalysisController::class, 'updateModels']);

Route::post('/projects/{project}/batches', [BatchController::class, 'store']);
Route::get('/batches/{batch}', [BatchController::class, 'show']);
Route::post('/batches/{batch}/cancel', [BatchController::class, 'cancel']);
Route::delete('/batches/{batch}', [BatchController::class, 'destroy']);

Route::post('/projects/{project}/compare', [CompareController::class, 'compare']);

Route::get('/docs', [DocsController::class, 'index']);
Route::get('/docs/{doc}', [DocsController::class, 'show'])->where('doc', '[a-z0-9-]+');
