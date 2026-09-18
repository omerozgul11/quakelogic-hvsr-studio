<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { api } from '@/api';
import type { ComponentKey, SpectraParams, SpectraResult, Ulid } from '@/api/types';
import Tabs from '@/components/ui/Tabs.vue';
import Button from '@/components/ui/Button.vue';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Select from '@/components/ui/Select.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import SpectraPlot from '@/components/plots/SpectraPlot.vue';
import SpectrogramPlot from '@/components/plots/SpectrogramPlot.vue';
import { useUnits } from '@/composables/useUnits';

interface Props { recordingId: Ulid; runId: Ulid | null; fs: number | null; channels?: Partial<Record<ComponentKey, string>>; units?: string; unitKind?: string }
const props = defineProps<Props>();
const unitsUi = useUnits();

const tab = ref<'fas' | 'psd' | 'spectrogram'>('fas');
const conv = computed(() => unitsUi.spectral(tab.value, props.unitKind, props.units));
const tabs = [{ key: 'fas', label: 'Amplitude spectra (FAS)' }, { key: 'psd', label: 'Power spectral density' }, { key: 'spectrogram', label: 'Spectrograms' }];
const params = reactive<SpectraParams>({ kind: 'fas', window_length_s: 60, overlap: 0.5, taper_percent: 5, detrend: 'linear', smoothing: { type: 'konno_ohmachi', bandwidth: 40 }, freq_min: 0.1, freq_max: 50, n_freq: 300, components: ['n', 'e', 'z'], t_start: null, t_end: null });
const result = ref<SpectraResult | null>(null);
const loading = ref(false);
const error = ref<unknown>(null);

const nyq = computed(() => (props.fs ? props.fs / 2 : null));
watch(nyq, (n) => { if (n && params.freq_max > n) params.freq_max = Math.floor(n * 100) / 100; }, { immediate: true });

async function compute() {
    loading.value = true;
    error.value = null;
    try {
        result.value = await api.recordings.spectra(props.recordingId, { ...params, kind: tab.value, run_id: props.runId, smoothing: tab.value === 'fas' ? params.smoothing : { type: 'none', bandwidth: params.smoothing.bandwidth } });
    } catch (e) { error.value = e; result.value = null; } finally { loading.value = false; }
}
watch(tab, () => { result.value = null; });
watch(() => props.runId, () => { result.value = null; });

const lineSeries = computed(() => {
    const out: Partial<Record<ComponentKey, (number | null)[]>> = {};
    if (!result.value || tab.value === 'spectrogram') return out;
    for (const c of ['n', 'e', 'z'] as ComponentKey[]) {
        const v = result.value.components[c];
        if (Array.isArray(v)) out[c] = conv.value.factor === 1 ? v : v.map((x) => (x === null ? null : x * conv.value.factor));
    }
    return out;
});
const specs = computed(() => {
    if (!result.value || tab.value !== 'spectrogram') return [];
    return (['n', 'e', 'z'] as ComponentKey[]).flatMap((c) => {
        const v = result.value!.components[c];
        if (!v || Array.isArray(v)) return [];
        const off = conv.value.dbOffset;
        return [{ c, t: v.t, f: v.f, db: off === 0 ? v.db : v.db.map((row) => row.map((x) => (x === null ? x : x + off))) }];
    });
});
</script>

<template>
    <div class="space-y-3">
        <Tabs v-model="tab" :tabs="tabs" small />
        <div class="flex flex-wrap items-end gap-3">
            <Field label="Window"><NumberInput v-model="params.window_length_s" :min="1" unit="s" /></Field>
            <Field label="Overlap"><NumberInput v-model="params.overlap" :min="0" :max="0.95" :step="0.05" /></Field>
            <Field label="Taper"><NumberInput v-model="params.taper_percent" :min="0" :max="50" unit="%" /></Field>
            <Field label="Detrend"><Select v-model="params.detrend" :options="[{ value: 'linear', label: 'Linear' }, { value: 'none', label: 'None' }]" /></Field>
            <template v-if="tab === 'fas'">
                <Field label="Smoothing"><Select v-model="params.smoothing.type" :options="[{ value: 'konno_ohmachi', label: 'Konno–Ohmachi' }, { value: 'none', label: 'None' }]" /></Field>
                <Field v-if="params.smoothing.type === 'konno_ohmachi'" label="b"><NumberInput v-model="params.smoothing.bandwidth" :min="5" :max="500" /></Field>
            </template>
            <Field label="f min"><NumberInput v-model="params.freq_min" :min="0.001" unit="Hz" /></Field>
            <Field label="f max"><NumberInput v-model="params.freq_max" :min="0.01" :max="nyq ?? undefined" unit="Hz" /></Field>
            <Field v-if="tab !== 'spectrogram'" label="Points"><NumberInput v-model="params.n_freq" :min="20" :max="5000" :step="10" /></Field>
            <Button variant="primary" :loading="loading" @click="compute">Compute</Button>
        </div>
        <p class="help">{{ tab === 'fas' ? `Mean Fourier amplitude spectrum |X(f)|·Δt over windows (${conv.label}), optionally Konno–Ohmachi smoothed on a log axis.` : tab === 'psd' ? `Welch power spectral density (${conv.label}) — separate from the amplitude spectrum used for H/V.` : `Short-time PSD per component (${conv.label}).` }}<span v-if="conv.converted" class="text-faint"> Displayed in US customary units; exports keep SI.</span></p>
        <ErrorBanner v-if="error" :error="error" />
        <template v-if="result && tab !== 'spectrogram' && result.frequency">
            <SpectraPlot :frequency="result.frequency" :series="lineSeries" :kind="tab" :units="conv.label" :channels="channels" :title="tab === 'fas' ? 'Fourier amplitude spectra' : 'Power spectral density (Welch)'" :export-name="tab" />
        </template>
        <template v-else-if="result && tab === 'spectrogram'">
            <SpectrogramPlot v-for="s in specs" :key="s.c" :t="s.t" :f="s.f" :db="s.db" :label="channels?.[s.c] ?? s.c.toUpperCase()" :units="conv.label" />
        </template>
        <p v-else-if="!loading" class="text-faint text-[12.5px]">Press Compute to calculate spectra for the {{ runId ? 'selected processing run' : 'raw recording' }}.</p>
    </div>
</template>
