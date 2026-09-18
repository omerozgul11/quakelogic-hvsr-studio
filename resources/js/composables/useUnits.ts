import { computed } from 'vue';
import { useAppStore } from '@/stores/app';
import type { ComponentKey, DisplayData } from '@/api/types';
import { amplitudeConversion, lengthFromDisplay, lengthToDisplay, lengthUnit, scaleValues, spectralLabel, type UnitSystem } from '@/utils/units';
import { fmtNum } from '@/utils/format';

/** Display-unit helpers bound to the user's unit-system preference (Settings → Units). */
export function useUnits() {
    const app = useAppStore();
    const system = computed<UnitSystem>(() => app.unitSystem);
    const lengthLabel = computed(() => lengthUnit(system.value));

    function formatLength(metres: number | null | undefined, sig = 5): string {
        const v = lengthToDisplay(metres, system.value);
        return v === null ? '—' : `${fmtNum(v, sig)} ${lengthLabel.value}`;
    }
    function amplitude(unitKind: string | null | undefined, units: string | null | undefined) {
        return amplitudeConversion(system.value, unitKind, units);
    }
    function amplitudeLabel(unitKind: string | null | undefined, units: string | null | undefined): string {
        return amplitude(unitKind, units).label;
    }
    function convertAmplitude(values: (number | null)[], unitKind: string | null | undefined, units: string | null | undefined): (number | null)[] {
        return scaleValues(values, amplitude(unitKind, units).factor);
    }
    /** Convert a waveform display payload (min/max envelope or samples) for plotting. */
    function convertDisplay(data: DisplayData | null, unitKind: string | null | undefined, units: string | null | undefined): DisplayData | null {
        if (!data) return null;
        const { factor, label } = amplitude(unitKind, units);
        if (factor === 1) return data;
        const components: DisplayData['components'] = {};
        for (const [k, c] of Object.entries(data.components)) {
            if (c) components[k as ComponentKey] = { t: c.t, v: scaleValues(c.v, factor) };
        }
        return { ...data, units: label, components };
    }
    function spectral(kind: 'fas' | 'psd' | 'spectrogram', unitKind: string | null | undefined, units: string | null | undefined) {
        const a = amplitude(unitKind, units);
        return { factor: kind === 'fas' ? a.factor : kind === 'psd' ? a.factor * a.factor : 1, dbOffset: kind === 'spectrogram' && a.factor !== 1 ? 20 * Math.log10(a.factor) : 0, label: spectralLabel(kind, a.label), converted: a.converted };
    }

    return { system, lengthLabel, formatLength, lengthToDisplay: (m: number | null | undefined) => lengthToDisplay(m, system.value), lengthFromDisplay: (v: number | null | undefined) => lengthFromDisplay(v, system.value), amplitude, amplitudeLabel, convertAmplitude, convertDisplay, spectral };
}
