<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\ActivityLog;
use App\Models\Analysis;
use App\Services\Projects\ProjectStorage;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\File;

/**
 * Survey / report details attached to an analysis (client, place, coordinates, weather, notes, up to two photos).
 */
class SurveyController extends Controller
{
    private const FIELDS = ['date', 'client', 'place_id', 'address', 'latitude', 'longitude', 'datum', 'elevation_m', 'weather', 'notes'];

    public function __construct(private readonly ProjectStorage $storage) {}

    public function show(Analysis $analysis): JsonResponse
    {
        return response()->json(self::normalise($analysis->survey));
    }

    public function update(Request $request, Analysis $analysis): JsonResponse
    {
        $data = $request->validate([
            'date' => ['nullable', 'date'],
            'client' => ['nullable', 'string', 'max:200'],
            'place_id' => ['nullable', 'string', 'max:200'],
            'address' => ['nullable', 'string', 'max:500'],
            'latitude' => ['nullable', 'numeric', 'between:-90,90'],
            'longitude' => ['nullable', 'numeric', 'between:-180,180'],
            'datum' => ['nullable', 'string', 'max:40'],
            'elevation_m' => ['nullable', 'numeric'],
            'weather' => ['nullable', 'string', 'max:200'],
            'notes' => ['nullable', 'string', 'max:5000'],
            'photo1' => ['nullable', 'file', 'mimes:jpg,jpeg,png', 'max:10240'],
            'photo2' => ['nullable', 'file', 'mimes:jpg,jpeg,png', 'max:10240'],
            'caption1' => ['nullable', 'string', 'max:200'],
            'caption2' => ['nullable', 'string', 'max:200'],
            'remove_photo1' => ['nullable', 'boolean'],
            'remove_photo2' => ['nullable', 'boolean'],
        ]);

        $survey = self::normalise($analysis->survey);
        foreach (self::FIELDS as $field) {
            if ($request->has($field)) {
                $survey[$field] = $data[$field] ?? null;
            }
        }
        foreach (['latitude', 'longitude', 'elevation_m'] as $num) {
            if ($survey[$num] !== null) {
                $survey[$num] = (float) $survey[$num];
            }
        }

        $dir = $this->storage->safe($this->analysisDir($analysis).'/survey');
        $photos = [];
        foreach ([1, 2] as $i) {
            $existing = $survey['photos'][$i - 1] ?? null;
            $remove = filter_var($data['remove_photo'.$i] ?? false, FILTER_VALIDATE_BOOL);
            $file = $request->file('photo'.$i);
            if ($file) {
                File::ensureDirectoryExists($dir);
                foreach (glob($dir.'/photo'.$i.'.*') ?: [] as $old) {
                    File::delete($old);
                }
                $ext = strtolower($file->getClientOriginalExtension() ?: 'jpg');
                $ext = $ext === 'jpeg' ? 'jpg' : $ext;
                $file->move($dir, 'photo'.$i.'.'.$ext);
                $photos[] = ['file' => 'survey/photo'.$i.'.'.$ext, 'caption' => $data['caption'.$i] ?? ($existing['caption'] ?? '')];
            } elseif ($existing && ! $remove) {
                if ($request->has('caption'.$i)) {
                    $existing['caption'] = $data['caption'.$i] ?? '';
                }
                $photos[] = $existing;
            } elseif ($existing && $remove) {
                foreach (glob($dir.'/photo'.$i.'.*') ?: [] as $old) {
                    File::delete($old);
                }
            }
        }
        $survey['photos'] = array_values($photos);

        $analysis->update(['survey' => $survey]);
        ActivityLog::record($analysis->project_id, 'analysis.survey_updated', $analysis, ['photos' => count($photos)]);

        return response()->json($survey);
    }

    public function photo(Analysis $analysis, int $index): mixed
    {
        $survey = self::normalise($analysis->survey);
        $photo = $survey['photos'][$index - 1] ?? null;
        abort_unless($photo, 404, 'No such photo.');
        $path = $this->storage->safe($this->analysisDir($analysis).'/'.$photo['file']);
        abort_unless(is_file($path), 404, 'Photo file is missing.');

        return response()->file($path);
    }

    /** @return array{date: ?string, client: ?string, place_id: ?string, address: ?string, latitude: ?float, longitude: ?float, datum: ?string, elevation_m: ?float, weather: ?string, notes: ?string, photos: array} */
    public static function normalise(?array $survey): array
    {
        $out = [];
        foreach (self::FIELDS as $field) {
            $out[$field] = $survey[$field] ?? null;
        }
        $out['datum'] = $out['datum'] ?? 'WGS84';
        $out['photos'] = array_values(array_filter($survey['photos'] ?? [], fn ($p) => is_array($p) && ! empty($p['file'])));

        return $out;
    }

    private function analysisDir(Analysis $analysis): string
    {
        return $analysis->result_dir ?: $this->storage->analysisDir($analysis->project, $analysis->ulid);
    }
}
