/**
 * Unit systems for display. Data are always stored and exported in SI / raw units;
 * conversion happens only when values are shown in the interface.
 */
export type UnitSystem = 'metric' | 'us';
export type PhysicalKind = 'velocity' | 'acceleration' | 'displacement';

export const UNIT_SYSTEMS: { value: UnitSystem; label: string; short: string }[] = [
    { value: 'metric', label: 'Metric (SI)', short: 'SI' },
    { value: 'us', label: 'US customary (SAE)', short: 'US' },
];

const M_PER_FT = 0.3048;
const IN_PER_M = 39.37007874015748;

/** Base-SI unit for each physical kind and the display unit in each system. */
const BASE: Record<PhysicalKind, { si: string; us: string; toUs: number }> = {
    displacement: { si: 'm', us: 'in', toUs: IN_PER_M },
    velocity: { si: 'm/s', us: 'in/s', toUs: IN_PER_M },
    acceleration: { si: 'm/s²', us: 'in/s²', toUs: IN_PER_M },
};

/** Multiplier from a written SI-family unit to the base SI unit of its kind. */
const PREFIX: Record<string, number> = { '': 1, m: 1e-3, c: 1e-2, u: 1e-6, 'µ': 1e-6, 'μ': 1e-6, n: 1e-9, k: 1e3 };

interface ParsedUnit { kind: PhysicalKind; toBase: number; canonical: string }

/**
 * Recognise common SI spellings: "m", "mm", "µm", "m/s", "cm/s", "nm/s", "m/s^2", "m/s²", "m/s2",
 * "mm/s^2", "gal" (cm/s²), "g" (9.80665 m/s²). Returns null for counts or unknown strings.
 */
export function parseSiUnit(units: string | null | undefined, kind?: string | null): ParsedUnit | null {
    if (!units) return null;
    const u = units.trim().replace(/\s+/g, '').replace('²', '^2').replace('/s2', '/s^2');
    if (/^gal$/i.test(u)) return { kind: 'acceleration', toBase: 1e-2, canonical: 'm/s²' };
    if (/^g$/.test(u)) return { kind: 'acceleration', toBase: 9.80665, canonical: 'm/s²' };
    const m = /^([mcunkµμ]?)m(\/s(\^2)?)?$/.exec(u);
    if (!m) return null;
    const factor = PREFIX[m[1] ?? ''] ?? 1;
    let k: PhysicalKind = m[3] ? 'acceleration' : m[2] ? 'velocity' : 'displacement';
    if (kind === 'velocity' || kind === 'acceleration' || kind === 'displacement') {
        // The declared kind wins when it is consistent with the unit's dimension.
        if ((kind === 'velocity' && k === 'velocity') || (kind === 'acceleration' && k === 'acceleration') || (kind === 'displacement' && k === 'displacement')) k = kind;
    }
    return { kind: k, toBase: factor, canonical: BASE[k].si };
}

export interface AmplitudeConversion { factor: number; label: string; converted: boolean }

/**
 * How to display amplitudes recorded in `units` (with declared `unitKind`) in the given system.
 * Raw counts, unknown units and metric display are returned unchanged (factor 1).
 */
export function amplitudeConversion(system: UnitSystem, unitKind: string | null | undefined, units: string | null | undefined): AmplitudeConversion {
    const label = units && units.trim() ? units.trim() : 'counts';
    if (system !== 'us' || !unitKind || unitKind === 'raw' || unitKind === 'unknown') return { factor: 1, label, converted: false };
    const parsed = parseSiUnit(units, unitKind);
    if (!parsed) return { factor: 1, label, converted: false };
    const base = BASE[parsed.kind];
    return { factor: parsed.toBase * base.toUs, label: base.us, converted: true };
}

export function scaleValues<T extends (number | null)[]>(values: T, factor: number): T {
    if (factor === 1) return values;
    return values.map((v) => (v === null || v === undefined ? v : v * factor)) as T;
}

/** Unit label for a spectral quantity derived from an amplitude unit. */
export function spectralLabel(kind: 'fas' | 'psd' | 'spectrogram', amplitudeUnit: string): string {
    if (kind === 'fas') return `${amplitudeUnit}·s`;
    if (kind === 'psd') return `${wrap(amplitudeUnit)}²/Hz`;
    return `dB re ${wrap(amplitudeUnit)}²/Hz`;
}
function wrap(u: string): string {
    return /[\/·\s]/.test(u) ? `(${u})` : u;
}

/** Length (elevation): metres stored; feet displayed in US mode. */
export function lengthToDisplay(metres: number | null | undefined, system: UnitSystem): number | null {
    if (metres === null || metres === undefined || Number.isNaN(metres)) return null;
    return system === 'us' ? metres / M_PER_FT : metres;
}
export function lengthFromDisplay(value: number | null | undefined, system: UnitSystem): number | null {
    if (value === null || value === undefined || Number.isNaN(value)) return null;
    return system === 'us' ? value * M_PER_FT : value;
}
export function lengthUnit(system: UnitSystem): string {
    return system === 'us' ? 'ft' : 'm';
}
