import type { HvsrParams, Step, StepOp, WindowsParams } from '@/api/types';

export interface StepDef {
    op: StepOp;
    label: string;
    help: string;
    defaults: Record<string, unknown>;
}

export const STEP_DEFS: StepDef[] = [
    { op: 'demean', label: 'Mean removal', help: 'Subtracts the arithmetic mean of each component.', defaults: {} },
    { op: 'detrend', label: 'Linear detrend', help: 'Removes a least-squares straight line from each component.', defaults: {} },
    { op: 'polynomial', label: 'Polynomial baseline', help: 'Removes a least-squares polynomial baseline. Orders above 3 can distort low frequencies — use with care.', defaults: { order: 2 } },
    { op: 'filter', label: 'Butterworth filter', help: 'High-pass, low-pass, band-pass or band-stop. Zero-phase applies the filter forward and backward (no phase distortion, doubled order).', defaults: { kind: 'bandpass', freq_low: 0.2, freq_high: 30, order: 4, zero_phase: true } },
    { op: 'notch', label: 'Notch (power line)', help: 'Narrow-band rejection at the given frequency and optional harmonics. Quality factor Q sets the notch width (f / Q).', defaults: { frequency: 60, quality: 30, harmonics: 1, zero_phase: true } },
    { op: 'taper', label: 'Taper', help: 'Cosine (Tukey) taper applied to each end of the record; percent is per side, as in ObsPy.', defaults: { percent: 5 } },
    { op: 'crop', label: 'Crop', help: 'Keeps only the time range between start and end (seconds from record start).', defaults: { start_s: 0, end_s: 60 } },
    { op: 'resample', label: 'Resample / decimate', help: 'Decimate applies an anti-alias filter and keeps every k-th sample (integer factors only). Polyphase handles rational ratios with a FIR anti-alias filter.', defaults: { target_rate: 50, method: 'decimate' } },
    { op: 'rotate', label: 'Rotate horizontals', help: 'Azimuth of the sensor N axis measured clockwise from true north. Rotates N/E to true north/east.', defaults: { azimuth_deg: 0 } },
    { op: 'remove_response', label: 'Remove instrument response', help: 'Deconvolves the instrument response from a StationXML file or manual poles & zeros. Requires metadata matching the recording channels.', defaults: { source: 'stationxml', path: '', output: 'VEL', water_level: 60, pre_filt: null, paz: { poles: [], zeros: [], gain: 1, sensitivity: 1 } } },
];

export function stepDef(op: StepOp): StepDef {
    return STEP_DEFS.find((d) => d.op === op)!;
}

export function newStep(op: StepOp): Step {
    return { op, enabled: true, params: JSON.parse(JSON.stringify(stepDef(op).defaults)) };
}

export function describeStep(s: Step): string {
    const p = s.params as Record<string, unknown>;
    switch (s.op) {
        case 'polynomial': return `order ${p.order}`;
        case 'filter': {
            const k = String(p.kind);
            const f = k === 'highpass' ? `${p.freq_low} Hz` : k === 'lowpass' ? `${p.freq_high} Hz` : `${p.freq_low}–${p.freq_high} Hz`;
            return `${k} ${f}, order ${p.order}, ${p.zero_phase ? 'zero-phase' : 'causal'}`;
        }
        case 'notch': return `${p.frequency} Hz, Q ${p.quality}${Number(p.harmonics) > 1 ? `, ${p.harmonics} harmonics` : ''}`;
        case 'taper': return `${p.percent}% per side`;
        case 'crop': return `${p.start_s}–${p.end_s} s`;
        case 'resample': return `${p.target_rate} Hz (${p.method})`;
        case 'rotate': return `azimuth ${p.azimuth_deg}°`;
        case 'remove_response': return `${p.source} → ${p.output}`;
        default: return '';
    }
}

export function defaultWindowsParams(): WindowsParams {
    return { mode: 'fixed', length_s: 60, overlap: 0.5, min_length_s: 30, max_length_s: 60, levels: { enabled: false, mode: 'ratio_rms', n: 0, e: 0, z: 0, ratio: 5 }, custom: [] };
}

/** Keep the legacy top-level aliases in step with the windows block (the engine accepts both). */
export function syncWindowAliases(p: HvsrParams): void {
    if (p.windows.mode === 'fixed') { p.window_length_s = p.windows.length_s; p.overlap = p.windows.overlap; }
    else { p.window_length_s = p.windows.max_length_s; p.overlap = 0; }
}

export function defaultHvsrParams(): HvsrParams {
    return {
        window_length_s: 60,
        overlap: 0.5,
        windows: defaultWindowsParams(),
        screening: {
            enabled: true,
            sta_lta: { enabled: true, sta_s: 2.0, lta_s: 30.0, min_ratio: 0.2, max_ratio: 2.5 },
            amplitude: { enabled: false, max_ratio_to_rms: 5.0 },
        },
        detrend: 'linear',
        taper_percent: 5,
        smoothing: { type: 'konno_ohmachi', bandwidth: 40 },
        freq_min: 0.2,
        freq_max: 30,
        n_freq: 300,
        horizontal_method: 'geometric_mean',
        combination_stage: 'after_smoothing',
        mean_method: 'geometric',
        peak: { search_min: 0.5, search_max: 20, min_prominence: 0 },
        vertical_floor: { relative: 1e-6, absolute: 1e-12 },
        min_valid_windows: 3,
        bootstrap: { enabled: true, n_resamples: 200 },
        azimuthal: { enabled: false, step_deg: 10 },
        sesame: true,
    };
}

export function mergeHvsrParams(p: Partial<HvsrParams> | null | undefined): HvsrParams {
    const d = defaultHvsrParams();
    if (!p) return d;
    const w: WindowsParams = { ...d.windows, ...(p.windows ?? {}), levels: { ...d.windows.levels, ...(p.windows?.levels ?? {}) }, custom: (p.windows?.custom ?? []).map((c) => [Number(c[0]), Number(c[1])] as [number, number]) };
    if (!p.windows) { w.length_s = p.window_length_s ?? d.window_length_s; w.overlap = p.overlap ?? d.overlap; }
    return {
        ...d, ...p,
        windows: w,
        screening: { ...d.screening, ...(p.screening ?? {}), sta_lta: { ...d.screening.sta_lta, ...(p.screening?.sta_lta ?? {}) }, amplitude: { ...d.screening.amplitude, ...(p.screening?.amplitude ?? {}) } },
        smoothing: { ...d.smoothing, ...(p.smoothing ?? {}) },
        peak: { ...d.peak, ...(p.peak ?? {}) },
        vertical_floor: { ...d.vertical_floor, ...(p.vertical_floor ?? {}) },
        bootstrap: { ...d.bootstrap, ...(p.bootstrap ?? {}) },
        azimuthal: { ...d.azimuthal, ...(p.azimuthal ?? {}) },
    };
}

/** Client-side sanity checks; the engine performs the authoritative validation. */
export function validateHvsrParams(p: HvsrParams, fs: number | null | undefined, duration: number | null | undefined): string[] {
    const errs: string[] = [];
    const w = p.windows ?? defaultWindowsParams();
    const longest = w.mode === 'fixed' ? w.length_s : w.mode === 'auto_variable' ? w.max_length_s : Math.max(0, ...w.custom.map((c) => c[1] - c[0]));
    if (w.mode === 'fixed') {
        if (w.length_s <= 0) errs.push('Window length must be positive.');
        if (w.overlap < 0 || w.overlap >= 1) errs.push('Overlap must be between 0 and 0.99.');
    } else if (w.mode === 'auto_variable') {
        if (w.min_length_s <= 0 || w.max_length_s < w.min_length_s) errs.push('Automatic windows need 0 < min length ≤ max length.');
    } else if (!w.custom.length) errs.push('Custom mode needs at least one window (draw one on the plot or load a window set).');
    else if (w.custom.some((c) => c[1] <= c[0])) errs.push('Every custom window needs end > start.');
    if (p.freq_min <= 0 || p.freq_max <= p.freq_min) errs.push('Frequency range must satisfy 0 < min < max.');
    if (fs && p.freq_max > fs / 2) errs.push(`Maximum frequency exceeds the Nyquist frequency (${fs / 2} Hz).`);
    if (longest > 0 && p.freq_min < 1 / longest) errs.push(`Minimum frequency is below the window resolution 1/T = ${(1 / longest).toFixed(4)} Hz.`);
    if (duration && longest > duration) errs.push('Window length exceeds the record duration.');
    if (p.peak.search_min >= p.peak.search_max) errs.push('Peak search range must satisfy min < max.');
    if (p.n_freq < 20 || p.n_freq > 5000) errs.push('Number of frequency points must be between 20 and 5000.');
    if (p.smoothing.type === 'konno_ohmachi' && (p.smoothing.bandwidth < 5 || p.smoothing.bandwidth > 500)) errs.push('Konno–Ohmachi bandwidth should be between 5 and 500.');
    if (p.screening.sta_lta.enabled && p.screening.sta_lta.sta_s >= p.screening.sta_lta.lta_s) errs.push('STA must be shorter than LTA.');
    return errs;
}
