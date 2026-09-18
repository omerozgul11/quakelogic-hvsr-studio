// Types mirroring docs/architecture.md (Laravel JSON API + Python engine shapes).

export type Ulid = string;
export type Severity = 'error' | 'warning' | 'info';
export type JobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
export type ComponentKey = 'n' | 'e' | 'z';

export interface Issue {
    code: string;
    severity: Severity;
    message: string;
    details?: Record<string, unknown> | null;
}

export interface EngineHealth {
    status: string;
    engine_version?: string;
    service_version?: string;
    python?: string;
    versions?: Record<string, string>;
    workers?: number;
    jobs_running?: number;
    message?: string;
}

export interface AppStatus {
    app_version: string;
    engine: EngineHealth;
    data_dir: string;
    theme_default?: string;
}

export interface Job {
    id: string;
    kind?: string;
    status: JobStatus;
    progress: number;
    message?: string | null;
    result?: unknown;
    error?: string | null;
    started_at?: string | null;
    finished_at?: string | null;
}

export interface Project {
    id: Ulid;
    name: string;
    slug: string;
    description?: string | null;
    folder?: string;
    settings?: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
    stations_count?: number;
    counts?: { stations: number; recordings: number; analyses: number };
    recordings_count?: number;
    analyses_count?: number;
    stations?: Station[];
    recordings?: Recording[];
    presets?: Preset[];
    batches?: Batch[];
}

export interface Station {
    id: Ulid;
    project_id?: Ulid;
    code: string;
    name?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    elevation?: number | null;
    orientation_deg?: number | null;
    notes?: string | null;
    created_at?: string;
    updated_at?: string;
}

export interface RecordingFile {
    id?: number;
    original_name: string;
    stored_path?: string;
    size_bytes: number;
    sha256: string;
    role?: string;
}

export interface RecordingMeta {
    fs: number;
    start_time: string;
    n_samples: number;
    units?: string;
    unit_kind?: string;
    channels?: Record<ComponentKey, string>;
    station?: string;
    network?: string;
    location?: string;
    orientation_deg?: number;
    is_synthetic?: boolean;
    [k: string]: unknown;
}

export interface Recording {
    id: Ulid;
    project_id?: Ulid;
    station_id?: Ulid | null;
    station?: Station | null;
    name: string;
    status: 'pending' | 'ready' | 'invalid';
    format?: 'ascii' | 'mseed' | 'saf' | 'seismic';
    sample_rate?: number | null;
    start_time?: string | null;
    duration_s?: number | null;
    n_samples?: number | null;
    units?: string | null;
    unit_kind?: string | null;
    import_settings?: Record<string, unknown> | null;
    validation?: { blocking: boolean; issues: Issue[] } | null;
    canonical_path?: string;
    meta?: RecordingMeta | null;
    is_synthetic?: boolean;
    notes?: string | null;
    files?: RecordingFile[];
    runs?: ProcessingRun[];
    analyses?: Analysis[];
    created_at?: string;
    updated_at?: string;
}

// ---- Inspect / import -----------------------------------------------------

export interface InspectColumn { index: number; name: string; numeric: boolean; sample: unknown[] }
export interface InspectAscii {
    encoding: string;
    delimiter: string;
    decimal: string;
    header_rows: number;
    comment_prefix: string | null;
    columns: InspectColumn[];
    n_rows_estimate: number;
    preview_lines: string[];
    preview_rows: unknown[][];
    time_column_guess: { index: number | null; kind: 'seconds' | 'datetime' | null; sample_rate_estimate: number | null } | null;
    sample_rate_hint: number | null;
}
export interface InspectTrace {
    id: string; network: string; station: string; location: string; channel: string;
    starttime: string; endtime: string; sampling_rate: number; npts: number; segments: number; has_gaps: boolean;
}
export interface InspectResult {
    path?: string;
    size_bytes: number;
    sha256: string;
    format: 'ascii' | 'mseed' | 'saf' | 'seismic' | 'unknown';
    ascii?: InspectAscii | null;
    saf?: { channels?: string[]; sample_rate?: number | null; start_time?: string | null; n_samples?: number | null; units?: string | null; header?: Record<string, string> } | null;
    mseed?: { traces: InspectTrace[] } | null;
    error?: string | null;
}

export interface Upload {
    upload_id: Ulid;
    id?: Ulid;
    name: string;
    size: number;
    sha256?: string;
    inspect: InspectResult;
}

export type TimeMode = 'sample_rate' | 'seconds_column' | 'datetime_column';

export interface AsciiImportSettings {
    delimiter: string;
    decimal: string;
    header_rows: number;
    comment_prefix: string | null;
    columns: Partial<Record<ComponentKey, number>>;
    time: { mode: TimeMode; sample_rate: number | null; column: number | null; datetime_format: string | null };
    start_time: string | null;
    units: string;
    unit_kind: string;
    scale_factor: number;
}

export interface MseedImportSettings {
    n: string | null;
    e: string | null;
    z: string | null;
    merge_policy: 'reject_gaps';
}

export interface ImportRequest {
    sources: { upload_id: Ulid; role: 'all' | ComponentKey }[];
    format: 'ascii' | 'mseed' | 'saf' | 'seismic';
    ascii?: AsciiImportSettings;
    mseed?: MseedImportSettings;
    metadata: { station: string; network: string; location: string; orientation_deg: number; is_synthetic: boolean };
}

export interface CreateRecordingRequest {
    name: string;
    station_id: Ulid | null;
    upload_ids: Ulid[];
    import: ImportRequest;
}

// ---- Data / spectra ---------------------------------------------------------

export interface ComponentSeries { t: number[]; v: number[] }
export interface DisplayData {
    fs: number;
    start_time: string;
    duration_s: number;
    n_samples: number;
    t_start: number;
    t_end: number;
    downsampled: boolean;
    n_display: number;
    method: string;
    units?: string;
    components: Partial<Record<ComponentKey, ComponentSeries>>;
}

export interface SpectraParams {
    kind: 'fas' | 'psd' | 'spectrogram';
    window_length_s: number;
    overlap: number;
    taper_percent: number;
    detrend: 'linear' | 'none';
    smoothing: { type: 'konno_ohmachi' | 'none'; bandwidth: number };
    freq_min: number;
    freq_max: number;
    n_freq: number;
    components: ComponentKey[];
    t_start: number | null;
    t_end: number | null;
    run_id?: Ulid | null;
}

export interface SpectraResult {
    frequency?: number[];
    components: Partial<Record<ComponentKey, number[] | { t: number[]; f: number[]; db: number[][] }>>;
    units?: string;
    definition?: string;
}

// ---- Processing -----------------------------------------------------------

export type StepOp = 'demean' | 'detrend' | 'polynomial' | 'filter' | 'notch' | 'taper' | 'crop' | 'resample' | 'rotate' | 'remove_response';

export interface Step {
    op: StepOp;
    enabled: boolean;
    params: Record<string, unknown>;
}

export interface StepWarning { step_index: number | null; code: string; message: string }

export interface PreviewResult {
    raw: DisplayData;
    processed: DisplayData;
    warnings: StepWarning[];
    applied: Step[];
    fs_out: number;
}

export interface FilterResponse {
    frequency: number[];
    magnitude_db: number[];
    phase_deg: number[];
    warnings: StepWarning[] | { code: string; message: string }[];
}

export interface ProcessingRun {
    id: Ulid;
    recording_id: Ulid;
    name: string;
    steps: Step[];
    applied?: Step[] | null;
    warnings?: StepWarning[] | null;
    status: JobStatus;
    job_id?: string | null;
    progress?: number;
    error?: string | null;
    output_path?: string | null;
    meta?: RecordingMeta | null;
    engine_version?: string | null;
    job?: Job | null;
    created_at?: string;
    updated_at?: string;
}

export interface Preset {
    id: Ulid;
    project_id?: Ulid | null;
    name: string;
    description?: string | null;
    steps: Step[];
    hvsr_params: HvsrParams;
    created_at?: string;
    updated_at?: string;
}

// ---- HVSR -----------------------------------------------------------------

export interface ScreeningParams {
    enabled: boolean;
    sta_lta: { enabled: boolean; sta_s: number; lta_s: number; min_ratio: number; max_ratio: number };
    amplitude: { enabled: boolean; max_ratio_to_rms: number };
}

export type WindowsMode = 'fixed' | 'auto_variable' | 'custom';

export interface WindowLevels {
    enabled: boolean;
    mode: 'absolute' | 'ratio_rms';
    n: number;
    e: number;
    z: number;
    ratio: number;
}

/** Window definition block (contract "Parity additions"). `length_s`/`overlap` mirror the top-level aliases. */
export interface WindowsParams {
    mode: WindowsMode;
    length_s: number;
    overlap: number;
    min_length_s: number;
    max_length_s: number;
    levels: WindowLevels;
    custom: [number, number][];
}

export interface HvsrParams {
    window_length_s: number;
    overlap: number;
    windows: WindowsParams;
    screening: ScreeningParams;
    detrend: 'linear' | 'none';
    taper_percent: number;
    smoothing: { type: 'konno_ohmachi' | 'none'; bandwidth: number };
    freq_min: number;
    freq_max: number;
    n_freq: number;
    horizontal_method: 'geometric_mean' | 'rms' | 'directional';
    combination_stage: 'after_smoothing' | 'before_smoothing';
    mean_method: 'geometric' | 'arithmetic' | 'median';
    peak: { search_min: number; search_max: number; min_prominence: number };
    vertical_floor: { relative: number; absolute: number };
    min_valid_windows: number;
    bootstrap: { enabled: boolean; n_resamples: number };
    azimuthal: { enabled: boolean; step_deg: number };
    sesame: boolean;
}

export type WindowOverrides = Record<string, { accepted: boolean; reason: string }>;

export interface WindowItem {
    index: number;
    start_s: number;
    end_s: number;
    accepted: boolean;
    reason: string | null;
    sta_lta_max?: number | null;
    sta_lta_min?: number | null;
    amp_ratio?: number | null;
    has_nan?: boolean;
    f0?: number | null;
    a0?: number | null;
    length_s?: number;
    color_index?: number;
}

export interface WindowsResult {
    windows: WindowItem[];
    counts: { total: number; accepted: number; rejected: number };
    screening_applied?: Record<string, unknown>;
}

export interface CurveSet {
    values: (number | null)[];
    lower: (number | null)[];
    upper: (number | null)[];
    band: string;
    sigma_ln?: (number | null)[];
}

export interface PeakCandidate { frequency: number; amplitude: number; prominence?: number; rank: number }

export interface SesameCriterion {
    id: string;
    label: string;
    passed: boolean | null;
    value: number | string | null;
    threshold: number | string | null;
    detail?: string;
}

export interface HvsrResult {
    engine_version: string;
    versions?: Record<string, string>;
    computed_at: string;
    elapsed_s?: number;
    random_seed: number | null;
    params: HvsrParams;
    input: { path: string; sha256?: string; fs: number; n_samples: number; duration_s: number; start_time: string; station?: string; is_synthetic?: boolean };
    frequency: number[];
    windows: { length_s: number; overlap: number; count_total: number; count_accepted: number; count_rejected: number; items: WindowItem[] };
    curves: { selected: 'geometric' | 'arithmetic' | 'median'; geometric: CurveSet; arithmetic: CurveSet; median: CurveSet };
    components: Partial<Record<ComponentKey | 'h', (number | null)[]>>;
    directional?: { n_over_z: CurveSet; e_over_z: CurveSet } | null;
    masking: { policy: string; bins_masked_any_window?: number; invalid_bins: number[]; min_valid_windows?: number };
    peaks: {
        search_range: [number, number];
        candidates: PeakCandidate[];
        selected: { frequency: number; amplitude: number; source: 'automatic' | 'manual' } | null;
        status: 'clear' | 'multiple' | 'none' | 'insufficient_data';
        message: string;
    };
    peak_variability: {
        window_f0: (number | null)[];
        window_a0?: (number | null)[];
        n: number;
        median: number | null;
        p16: number | null;
        p84: number | null;
        std: number | null;
        std_ln: number | null;
        definition: string;
        bootstrap: { n_resamples: number; seed: number; f0_p2_5: number | null; f0_p50: number | null; f0_p97_5: number | null; a0_p2_5: number | null; a0_p97_5: number | null; definition: string } | null;
    };
    sesame: {
        reference: string;
        f0: number | null;
        a0: number | null;
        reliability: SesameCriterion[];
        clarity: SesameCriterion[];
        reliability_passed: boolean;
        clarity_passed_count: number;
        clarity_passed: boolean;
    } | null;
    quality_flags: Issue[];
    interpretation_notes?: string[];
    azimuthal?: { azimuths: number[]; frequency: number[]; matrix: (number | null)[][]; peak_frequency: (number | null)[]; peak_amplitude: (number | null)[] } | null;
    /** Per-window H/V matrix (rows = windows in time order, NaN/null rows for rejected windows). */
    time_frequency?: { times_s: number[]; frequency: number[]; matrix: (number | null)[][] } | null;
    /** SESAME reliability limit 10 / (longest window length). */
    t10_hz?: number | null;
}

// ---- Forward modelling ------------------------------------------------------

export interface ModelLayer {
    thickness_m: number | null;
    vs: number;
    vp: number | null;
    poisson: number | null;
    density: number;
    qs?: number | null;
    qp?: number | null;
    depth_top_m?: number;
    depth_bottom_m?: number | null;
}

export interface ModelRequest {
    layers: ModelLayer[];
    freq_min: number;
    freq_max: number;
    n_freq: number;
    vs30_offset_m: number;
}

export interface ModelResponse {
    frequency: number[];
    hvsr: (number | null)[];
    t_sh?: (number | null)[];
    t_p?: (number | null)[];
    layers: ModelLayer[];
    vs30: number | null;
    vseq: { value: number | null; depth_m: number | null; definition: string } | null;
    f0_model: number | null;
    method: string;
    notes: string[];
}

export interface GroundModel {
    id: string;
    name: string;
    layers: ModelLayer[];
    vs30_offset_m: number;
    created_at: string;
}

// ---- Curves / survey / window sets --------------------------------------------

export interface ImportedCurve {
    frequency: number[];
    values: (number | null)[];
    lower?: (number | null)[] | null;
    upper?: (number | null)[] | null;
    name: string;
    format: 'geopsy_hv' | 'csv' | string;
}

export interface SurveyPhoto { file: string; caption?: string; url?: string }
export interface Survey {
    date?: string | null;
    client?: string | null;
    place_id?: string | null;
    address?: string | null;
    latitude?: number | null;
    longitude?: number | null;
    datum?: string | null;
    elevation_m?: number | null;
    weather?: string | null;
    notes?: string | null;
    photos?: SurveyPhoto[];
}

export interface WindowSetExport {
    mode?: WindowsMode;
    params?: Partial<WindowsParams>;
    windows: { start_s: number; end_s: number; accepted?: boolean; reason?: string | null }[];
}
export interface WindowImportResult { custom: [number, number][]; window_overrides: WindowOverrides }
export interface SamplesResponse { fs: number; t0: number; values: number[] }

export interface WindowCurves { frequency: number[]; curves: (number | null)[][]; accepted: boolean[] }

export interface AnalysisSummary {
    f0?: number | null;
    a0?: number | null;
    peak_status?: string;
    peak_source?: string;
    count_accepted?: number;
    count_total?: number;
    sesame_reliability?: boolean | null;
    sesame_clarity_count?: number | null;
    quality_flags?: Issue[];
    [k: string]: unknown;
}

export interface Analysis {
    id: Ulid;
    project_id?: Ulid;
    recording_id: Ulid;
    recording?: Recording | null;
    processing_run_id?: Ulid | null;
    name: string;
    params: HvsrParams;
    window_overrides?: WindowOverrides | null;
    manual_peak?: { frequency: number } | null;
    random_seed?: number | null;
    status: JobStatus;
    job_id?: string | null;
    progress?: number;
    error?: string | null;
    result_dir?: string;
    summary?: AnalysisSummary | null;
    engine_version?: string | null;
    report_path?: string | null;
    report_status?: JobStatus | null;
    report_job_id?: string | null;
    job?: Job | null;
    result?: HvsrResult | null;
    survey?: Survey | null;
    models?: GroundModel[] | null;
    created_at?: string;
    updated_at?: string;
}

export interface CreateAnalysisRequest {
    name: string;
    run_id: Ulid | null;
    params: HvsrParams;
    window_overrides: WindowOverrides;
    manual_peak: { frequency: number } | null;
    random_seed: number | null;
}

// ---- Batches / compare ----------------------------------------------------

export interface BatchItem {
    id: number;
    recording_id: Ulid;
    recording?: Recording | null;
    processing_run_id?: Ulid | null;
    analysis_id?: Ulid | null;
    analysis?: Analysis | null;
    position: number;
    status: 'queued' | 'running' | 'done' | 'failed' | 'skipped' | 'cancelled';
    error?: string | null;
    progress?: number;
}

export interface Batch {
    id: Ulid;
    project_id?: Ulid;
    name: string;
    preset_id?: Ulid | null;
    preset?: Preset | null;
    run_steps: boolean;
    status: 'queued' | 'running' | 'done' | 'cancelled';
    current_index?: number;
    items: BatchItem[];
    created_at?: string;
    updated_at?: string;
}

export interface CompareEntry {
    analysis_id: Ulid;
    name: string;
    recording_id: Ulid;
    recording_name?: string | null;
    station_code?: string | null;
    run_name?: string | null;
    mean_method?: string;
    peak_status?: string | null;
    windows?: { accepted: number; total: number } | null;
    sesame?: { reliability_passed: boolean | null; clarity_passed_count: number | null; clarity_passed: boolean | null } | null;
    quality_flags?: Issue[];
    params?: Record<string, unknown>;
    frequency: number[];
    curve: (number | null)[];
    lower: (number | null)[];
    upper: (number | null)[];
    peak: { frequency: number; amplitude: number; source?: string } | null;
    band?: string;
}

export interface ActivityEntry {
    id: number;
    subject_type: string;
    subject_id: string | number;
    action: string;
    details?: Record<string, unknown> | null;
    created_at: string;
}

export type Settings = Record<string, unknown> & {
    theme_default?: string;
    unit_system?: 'metric' | 'us';
    default_preset_id?: Ulid | null;
    engine_url?: string;
    data_dir?: string;
};

export type ExportKind = 'hvsr-csv' | 'windows-csv' | 'spectra-csv' | 'summary-csv' | 'summary-json' | 'config-json' | 'azimuthal-csv' | 'geopsy-hv' | 'windows-json';
export type FigureKind = 'hvsr' | 'spectra' | 'windows' | 'azimuthal' | 'peak_distribution';

export interface DocInfo {
    key: string;
    title: string;
    available: boolean;
}
