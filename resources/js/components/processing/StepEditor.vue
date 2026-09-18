<script setup lang="ts">
import { computed } from 'vue';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Select from '@/components/ui/Select.vue';
import Toggle from '@/components/ui/Toggle.vue';
import { stepDef } from './defaults';
import type { Step } from '@/api/types';

interface Props { step: Step; fs?: number | null; duration?: number | null }
const props = defineProps<Props>();
const emit = defineEmits<{ change: [] }>();

const p = computed(() => props.step.params as Record<string, unknown>);
const nyq = computed(() => (props.fs ? props.fs / 2 : null));
function set(key: string, v: unknown) {
    (props.step.params as Record<string, unknown>)[key] = v;
    emit('change');
}
function num(key: string): number | null {
    const v = p.value[key];
    return typeof v === 'number' ? v : null;
}
function bool(key: string): boolean {
    return !!p.value[key];
}
const def = computed(() => stepDef(props.step.op));

const filterWarn = computed(() => {
    if (props.step.op !== 'filter' || !nyq.value) return null;
    const k = String(p.value.kind);
    const lo = num('freq_low');
    const hi = num('freq_high');
    if ((k === 'highpass' || k === 'bandpass' || k === 'bandstop') && lo !== null && lo >= nyq.value) return `Low cutoff must be below Nyquist (${nyq.value} Hz).`;
    if ((k === 'lowpass' || k === 'bandpass' || k === 'bandstop') && hi !== null && hi >= nyq.value) return `High cutoff must be below Nyquist (${nyq.value} Hz).`;
    if ((k === 'bandpass' || k === 'bandstop') && lo !== null && hi !== null && lo >= hi) return 'Low cutoff must be below the high cutoff.';
    return null;
});
function pairsToText(v: unknown): string {
    if (!Array.isArray(v)) return '';
    return v.map((x) => (Array.isArray(x) ? `${x[0]},${x[1]}` : '')).join('\n');
}
function paz(): Record<string, unknown> {
    const params = props.step.params as Record<string, unknown>;
    if (!params.paz || typeof params.paz !== 'object') params.paz = { poles: [], zeros: [], gain: 1, sensitivity: 1 };
    return params.paz as Record<string, unknown>;
}
function setPaz(key: 'poles' | 'zeros', text: string) {
    paz()[key] = text.split(/\n+/).map((l) => l.trim()).filter(Boolean).map((l) => {
        const [a, b] = l.split(/[,\s]+/).map(Number);
        return [Number.isFinite(a) ? a : 0, Number.isFinite(b) ? b : 0];
    });
    emit('change');
}
function pazNum(key: string): number | null {
    const v = paz()[key];
    return typeof v === 'number' ? v : null;
}
function setPazNum(key: string, v: number | null) {
    paz()[key] = v;
    emit('change');
}
</script>

<template>
    <div class="space-y-2.5">
        <p class="help !mt-0">{{ def.help }}</p>

        <template v-if="step.op === 'polynomial'">
            <Field label="Polynomial order" inline><NumberInput :model-value="num('order')" :min="1" :max="10" :step="1" @update:model-value="set('order', $event)" /></Field>
        </template>

        <template v-else-if="step.op === 'filter'">
            <Field label="Type" inline>
                <Select :model-value="String(p.kind)" :options="[{ value: 'highpass', label: 'High-pass' }, { value: 'lowpass', label: 'Low-pass' }, { value: 'bandpass', label: 'Band-pass' }, { value: 'bandstop', label: 'Band-stop' }]" @update:model-value="set('kind', $event)" />
            </Field>
            <Field v-if="p.kind !== 'lowpass'" label="Low cutoff" inline><NumberInput :model-value="num('freq_low')" :min="0" unit="Hz" @update:model-value="set('freq_low', $event)" /></Field>
            <Field v-if="p.kind !== 'highpass'" label="High cutoff" inline><NumberInput :model-value="num('freq_high')" :min="0" unit="Hz" @update:model-value="set('freq_high', $event)" /></Field>
            <Field label="Order" inline><NumberInput :model-value="num('order')" :min="1" :max="16" :step="1" @update:model-value="set('order', $event)" /></Field>
            <Toggle :model-value="bool('zero_phase')" label="Zero-phase (forward–backward)" small @update:model-value="set('zero_phase', $event)" />
            <p v-if="filterWarn" class="text-[11.5px] text-bad-500">{{ filterWarn }}</p>
            <p v-else-if="nyq" class="help">Nyquist frequency: {{ nyq }} Hz.</p>
        </template>

        <template v-else-if="step.op === 'notch'">
            <Field label="Frequency" inline><NumberInput :model-value="num('frequency')" :min="0" unit="Hz" @update:model-value="set('frequency', $event)" /></Field>
            <Field label="Quality factor Q" inline><NumberInput :model-value="num('quality')" :min="1" @update:model-value="set('quality', $event)" /></Field>
            <Field label="Harmonics" inline><NumberInput :model-value="num('harmonics')" :min="1" :max="20" :step="1" @update:model-value="set('harmonics', $event)" /></Field>
            <Toggle :model-value="bool('zero_phase')" label="Zero-phase" small @update:model-value="set('zero_phase', $event)" />
        </template>

        <template v-else-if="step.op === 'taper'">
            <Field label="Taper per side" inline><NumberInput :model-value="num('percent')" :min="0" :max="50" unit="%" @update:model-value="set('percent', $event)" /></Field>
        </template>

        <template v-else-if="step.op === 'crop'">
            <Field label="Start" inline><NumberInput :model-value="num('start_s')" :min="0" unit="s" @update:model-value="set('start_s', $event)" /></Field>
            <Field label="End" inline><NumberInput :model-value="num('end_s')" :min="0" unit="s" @update:model-value="set('end_s', $event)" /></Field>
            <p v-if="duration" class="help">Record duration: {{ duration.toFixed(2) }} s.</p>
        </template>

        <template v-else-if="step.op === 'resample'">
            <Field label="Target rate" inline><NumberInput :model-value="num('target_rate')" :min="0.001" unit="Hz" @update:model-value="set('target_rate', $event)" /></Field>
            <Field label="Method" inline>
                <Select :model-value="String(p.method)" :options="[{ value: 'decimate', label: 'Decimate (integer)' }, { value: 'polyphase', label: 'Polyphase (rational)' }]" @update:model-value="set('method', $event)" />
            </Field>
            <p v-if="fs" class="help">Current rate: {{ fs }} Hz{{ num('target_rate') && fs % (num('target_rate') as number) !== 0 && p.method === 'decimate' ? ' — not an integer factor; choose polyphase.' : '' }}</p>
        </template>

        <template v-else-if="step.op === 'rotate'">
            <Field label="Sensor N azimuth" inline><NumberInput :model-value="num('azimuth_deg')" :min="-360" :max="360" unit="°" @update:model-value="set('azimuth_deg', $event)" /></Field>
        </template>

        <template v-else-if="step.op === 'remove_response'">
            <Field label="Source" inline>
                <Select :model-value="String(p.source)" :options="[{ value: 'stationxml', label: 'StationXML file' }, { value: 'paz', label: 'Poles & zeros' }]" @update:model-value="set('source', $event)" />
            </Field>
            <Field v-if="p.source === 'stationxml'" label="StationXML path" help="Absolute path to a StationXML file on this computer whose channel codes match the recording.">
                <input class="input num" :value="String(p.path ?? '')" placeholder="C:\data\station.xml" @input="set('path', ($event.target as HTMLInputElement).value)" />
            </Field>
            <template v-else>
                <Field label="Poles (re,im per line)" help="One complex pole per line, e.g. -4.44,4.44">
                    <textarea class="input num h-20" :value="pairsToText((p.paz as Record<string, unknown>)?.poles)" @input="setPaz('poles', ($event.target as HTMLTextAreaElement).value)" />
                </Field>
                <Field label="Zeros (re,im per line)">
                    <textarea class="input num h-16" :value="pairsToText((p.paz as Record<string, unknown>)?.zeros)" @input="setPaz('zeros', ($event.target as HTMLTextAreaElement).value)" />
                </Field>
                <Field label="Gain (A0)" inline><NumberInput :model-value="pazNum('gain')" @update:model-value="setPazNum('gain', $event)" /></Field>
                <Field label="Sensitivity" inline><NumberInput :model-value="pazNum('sensitivity')" @update:model-value="setPazNum('sensitivity', $event)" /></Field>
            </template>
            <Field label="Output" inline>
                <Select :model-value="String(p.output)" :options="[{ value: 'DISP', label: 'Displacement' }, { value: 'VEL', label: 'Velocity' }, { value: 'ACC', label: 'Acceleration' }]" @update:model-value="set('output', $event)" />
            </Field>
            <Field label="Water level" inline><NumberInput :model-value="num('water_level')" :min="0" unit="dB" @update:model-value="set('water_level', $event)" /></Field>
        </template>

        <p v-else class="help">No parameters.</p>
    </div>
</template>
