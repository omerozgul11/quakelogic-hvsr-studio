<script setup lang="ts">
import { ref } from 'vue';
import { ChevronDown, ChevronRight } from 'lucide-vue-next';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Select from '@/components/ui/Select.vue';
import Toggle from '@/components/ui/Toggle.vue';
import type { HvsrParams } from '@/api/types';
import Tabs from '@/components/ui/Tabs.vue';
import { syncWindowAliases } from '@/components/processing/defaults';

interface Props { params: HvsrParams; fs?: number | null; duration?: number | null; windowsOnly?: boolean }
const props = defineProps<Props>();
const emit = defineEmits<{ change: [] }>();
const advanced = ref(false);
const p = props.params;
function ch() { syncWindowAliases(p); emit('change'); }
const modeTabs = [{ key: 'fixed', label: 'Fixed' }, { key: 'auto_variable', label: 'Automatic' }, { key: 'custom', label: 'Custom' }];
const t10 = () => { const w = p.windows; const L = w.mode === 'fixed' ? w.length_s : w.mode === 'auto_variable' ? w.max_length_s : Math.max(0, ...w.custom.map((c) => c[1] - c[0])); return L > 0 ? 10 / L : null; };
</script>

<template>
    <div class="space-y-5 text-[12.5px]">
        <section class="space-y-2.5">
            <h3 class="eyebrow">Windows</h3>
            <Tabs :model-value="p.windows.mode" :tabs="modeTabs" small @update:model-value="(m) => { p.windows.mode = m as typeof p.windows.mode; ch(); }" />
            <template v-if="p.windows.mode === 'fixed'">
                <div class="grid grid-cols-2 gap-2.5">
                    <Field label="Length" hint="Each window is analysed separately. Frequency resolution is 1/T, so longer windows resolve lower frequencies; more windows reduce scatter."><NumberInput v-model="p.windows.length_s" :min="1" unit="s" @update:model-value="ch" /></Field>
                    <Field label="Overlap" hint="Fraction of each window shared with the next (0.5 = 50 %)."><NumberInput v-model="p.windows.overlap" :min="0" :max="0.95" :step="0.05" unit="frac" @update:model-value="ch" /></Field>
                </div>
                <p class="help">Resolution 1/T = {{ (1 / Math.max(p.windows.length_s, 1e-9)).toFixed(4) }} Hz<template v-if="duration"> · about {{ Math.max(0, Math.floor((duration - p.windows.length_s) / (p.windows.length_s * (1 - p.windows.overlap)) + 1)) }} windows</template> · T10 = {{ t10()?.toFixed(3) ?? '—' }} Hz</p>
            </template>
            <template v-else-if="p.windows.mode === 'auto_variable'">
                <div class="grid grid-cols-2 gap-2.5">
                    <Field label="Min length" hint="Shortest window the automatic packing may create."><NumberInput v-model="p.windows.min_length_s" :min="1" unit="s" @update:model-value="ch" /></Field>
                    <Field label="Max length" hint="Longest window; the quiet parts of the record are filled with the longest possible windows first."><NumberInput v-model="p.windows.max_length_s" :min="1" unit="s" @update:model-value="ch" /></Field>
                </div>
                <p class="help">Windows of variable length (min–max) are packed into the quiet parts of the record — quiet = amplitude below the levels below and STA/LTA inside its band. T10 = {{ t10()?.toFixed(3) ?? '—' }} Hz.</p>
            </template>
            <template v-else>
                <p class="help">{{ p.windows.custom.length }} custom window{{ p.windows.custom.length === 1 ? '' : 's' }}. Draw windows with <em>Free selection</em> on the plot, edit start/end in the table, or load a saved window set. T10 = {{ t10()?.toFixed(3) ?? '—' }} Hz.</p>
            </template>
            <Toggle v-model="p.windows.levels.enabled" label="Use amplitude levels" small help="Samples above the level count as noisy: in Automatic mode they are avoided, in Fixed/Custom mode windows containing them are rejected." @update:model-value="ch" />
            <div v-if="p.windows.levels.enabled" class="space-y-2 pl-1">
                <Field label="Level mode"><Select v-model="p.windows.levels.mode" :options="[{ value: 'ratio_rms', label: 'k × RMS of each component' }, { value: 'absolute', label: 'Absolute level per channel' }]" @update:model-value="ch" /></Field>
                <div v-if="p.windows.levels.mode === 'ratio_rms'" class="grid grid-cols-2 gap-2.5"><Field label="k"><NumberInput v-model="p.windows.levels.ratio" :min="0.5" @update:model-value="ch" /></Field></div>
                <div v-else class="grid grid-cols-3 gap-2">
                    <Field label="N"><NumberInput v-model="p.windows.levels.n" :min="0" @update:model-value="ch" /></Field>
                    <Field label="E"><NumberInput v-model="p.windows.levels.e" :min="0" @update:model-value="ch" /></Field>
                    <Field label="Z"><NumberInput v-model="p.windows.levels.z" :min="0" @update:model-value="ch" /></Field>
                </div>
            </div>
        </section>

        <section class="space-y-2.5">
            <h3 class="eyebrow">Transient screening</h3>
            <Toggle v-model="p.screening.enabled" label="Reject noisy windows automatically" small @update:model-value="ch" />
            <template v-if="p.screening.enabled">
                <Toggle v-model="p.screening.sta_lta.enabled" label="STA/LTA anti-trigger" small help="A window is rejected when the STA/LTA ratio of any component leaves [min, max] inside the window (Geopsy-style anti-trigger)." @update:model-value="ch" />
                <div v-if="p.screening.sta_lta.enabled" class="grid grid-cols-2 gap-2.5 pl-1">
                    <Field label="STA" hint="Short-term average length."><NumberInput v-model="p.screening.sta_lta.sta_s" :min="0.05" unit="s" @update:model-value="ch" /></Field>
                    <Field label="LTA" hint="Long-term average length."><NumberInput v-model="p.screening.sta_lta.lta_s" :min="1" unit="s" @update:model-value="ch" /></Field>
                    <Field label="Min ratio" hint="Windows where STA/LTA drops below this value are rejected (quiet gaps)."><NumberInput v-model="p.screening.sta_lta.min_ratio" :min="0" @update:model-value="ch" /></Field>
                    <Field label="Max ratio" hint="Windows where STA/LTA exceeds this value are rejected (transients)."><NumberInput v-model="p.screening.sta_lta.max_ratio" :min="0" @update:model-value="ch" /></Field>
                </div>
                <Toggle v-model="p.screening.amplitude.enabled" label="Amplitude criterion" small help="Reject windows whose peak absolute amplitude exceeds k × the RMS of the whole component." @update:model-value="ch" />
                <div v-if="p.screening.amplitude.enabled" class="grid grid-cols-2 gap-2.5 pl-1">
                    <Field label="Max |x| / RMS" hint="k factor of the amplitude criterion."><NumberInput v-model="p.screening.amplitude.max_ratio_to_rms" :min="1" @update:model-value="ch" /></Field>
                </div>
            </template>
        </section>

        <template v-if="!windowsOnly">
            <section class="space-y-2.5">
                <h3 class="eyebrow">Spectra & smoothing</h3>
                <div class="grid grid-cols-2 gap-2.5">
                    <Field label="Detrend" hint="Per-window least-squares line removal before the FFT."><Select v-model="p.detrend" :options="[{ value: 'linear', label: 'Linear' }, { value: 'none', label: 'None' }]" @update:model-value="ch" /></Field>
                    <Field label="Taper" hint="Cosine (Tukey) taper applied to each side of every window."><NumberInput v-model="p.taper_percent" :min="0" :max="50" unit="%" @update:model-value="ch" /></Field>
                    <Field label="Smoothing" hint="Konno–Ohmachi (1998) smoothing has constant width on a log-frequency axis."><Select v-model="p.smoothing.type" :options="[{ value: 'konno_ohmachi', label: 'Konno–Ohmachi' }, { value: 'none', label: 'None' }]" @update:model-value="ch" /></Field>
                    <Field v-if="p.smoothing.type === 'konno_ohmachi'" label="Bandwidth b" hint="b = 40 is the common default; smaller b smooths more."><NumberInput v-model="p.smoothing.bandwidth" :min="5" :max="500" @update:model-value="ch" /></Field>
                    <Field label="f min" hint="Lower end of the analysis frequency axis."><NumberInput v-model="p.freq_min" :min="0.001" unit="Hz" @update:model-value="ch" /></Field>
                    <Field label="f max" :hint="fs ? `Upper end of the analysis axis (Nyquist ${fs / 2} Hz).` : 'Upper end of the analysis axis.'"><NumberInput v-model="p.freq_max" :min="0.01" unit="Hz" @update:model-value="ch" /></Field>
                    <Field label="Frequency points" hint="Number of log-spaced output frequencies."><NumberInput v-model="p.n_freq" :min="20" :max="5000" :step="10" @update:model-value="ch" /></Field>
                </div>
            </section>

            <section class="space-y-2.5">
                <h3 class="eyebrow">H/V definition</h3>
                <Field label="Horizontal combination" hint="How the two horizontal spectra are merged before dividing by the vertical."><Select v-model="p.horizontal_method" :options="[{ value: 'geometric_mean', label: 'Geometric mean √(|N|·|E|)' }, { value: 'rms', label: 'RMS √((|N|²+|E|²)/2)' }, { value: 'directional', label: 'Directional |N|/|Z|, |E|/|Z|' }]" @update:model-value="ch" /></Field>
                <Field label="Curve statistic" hint="All three statistics are computed; this one is displayed and used for peak picking. Dispersion bands are ±1σ (log or linear) or 16–84 %, not confidence intervals."><Select v-model="p.mean_method" :options="[{ value: 'geometric', label: 'Geometric (log) mean' }, { value: 'arithmetic', label: 'Arithmetic mean' }, { value: 'median', label: 'Median' }]" @update:model-value="ch" /></Field>
            </section>

            <section class="space-y-2.5">
                <h3 class="eyebrow">Peak search</h3>
                <div class="grid grid-cols-2 gap-2.5">
                    <Field label="From" hint="Only local maxima inside this range are peak candidates."><NumberInput v-model="p.peak.search_min" :min="0.001" unit="Hz" @update:model-value="ch" /></Field>
                    <Field label="To"><NumberInput v-model="p.peak.search_max" :min="0.01" unit="Hz" @update:model-value="ch" /></Field>
                    <Field label="Min prominence" hint="Candidates with a smaller prominence are ignored (0 = keep all local maxima)."><NumberInput v-model="p.peak.min_prominence" :min="0" @update:model-value="ch" /></Field>
                    <Field label="Min valid windows" hint="Frequency bins with fewer valid windows are flagged invalid."><NumberInput v-model="p.min_valid_windows" :min="1" :step="1" @update:model-value="ch" /></Field>
                </div>
            </section>

            <section class="space-y-2.5">
                <h3 class="eyebrow">Variability & criteria</h3>
                <Toggle v-model="p.bootstrap.enabled" label="Bootstrap interval of the peak" small help="Resamples the accepted windows to estimate a percentile interval of f0 and A0; the seed is stored." @update:model-value="ch" />
                <div v-if="p.bootstrap.enabled" class="grid grid-cols-2 gap-2.5 pl-1"><Field label="Resamples"><NumberInput v-model="p.bootstrap.n_resamples" :min="20" :max="5000" :step="10" @update:model-value="ch" /></Field></div>
                <Toggle v-model="p.sesame" label="Evaluate SESAME (2004) criteria" small help="Reliability and clear-peak criteria, reported one by one." @update:model-value="ch" />
                <Toggle v-model="p.azimuthal.enabled" label="Azimuthal H/V" small help="H/V of a single rotated horizontal from 0° to 180°." @update:model-value="ch" />
                <div v-if="p.azimuthal.enabled" class="grid grid-cols-2 gap-2.5 pl-1"><Field label="Azimuth step"><NumberInput v-model="p.azimuthal.step_deg" :min="1" :max="90" unit="°" @update:model-value="ch" /></Field></div>
            </section>

            <section class="space-y-2.5">
                <button class="flex items-center gap-1 eyebrow hover:text-ui" @click="advanced = !advanced"><component :is="advanced ? ChevronDown : ChevronRight" class="size-3.5" />Advanced</button>
                <template v-if="advanced">
                    <Field label="Combination stage" hint="Default: each component spectrum is smoothed, then horizontals are combined and divided by the smoothed vertical. “Before” combines raw amplitude spectra first (hvsrpy-style)."><Select v-model="p.combination_stage" :options="[{ value: 'after_smoothing', label: 'After smoothing (default)' }, { value: 'before_smoothing', label: 'Before smoothing' }]" @update:model-value="ch" /></Field>
                    <div class="grid grid-cols-2 gap-2.5">
                        <Field label="Vertical floor (rel.)" hint="Bins where the smoothed vertical amplitude falls below relative × max are masked instead of producing spurious ratios."><NumberInput v-model="p.vertical_floor.relative" :min="0" @update:model-value="ch" /></Field>
                        <Field label="Vertical floor (abs.)" hint="Absolute floor for the smoothed vertical amplitude."><NumberInput v-model="p.vertical_floor.absolute" :min="0" @update:model-value="ch" /></Field>
                    </div>
                </template>
            </section>
        </template>
    </div>
</template>
