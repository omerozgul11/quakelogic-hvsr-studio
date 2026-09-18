<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { Play, Pause, Square, Rewind, FastForward, Bookmark, Volume2 } from 'lucide-vue-next';
import { api } from '@/api';
import type { ComponentKey, Ulid } from '@/api/types';
import Button from '@/components/ui/Button.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import { useToastStore } from '@/stores/toast';
import { fmtDuration } from '@/utils/format';

/**
 * Seismogram sonification player (QLExplorer-style): the recorded samples are re-clocked at the
 * "playback frequency" (e.g. 100 Hz data played at 1000 Hz = 10× faster) so that transients become
 * audible. Uses the Web Audio API only; nothing leaves the machine.
 */
interface Props { recordingId: Ulid; runId?: Ulid | null; fs: number | null; duration: number | null; channels?: Partial<Record<ComponentKey, string>> }
const props = withDefaults(defineProps<Props>(), { runId: null });
const emit = defineEmits<{ time: [t: number | null]; bookmark: [t: number] }>();
const toast = useToastStore();

const channel = ref<ComponentKey>('z');
const playbackFreq = ref<number | null>(1000);
const volume = ref(0.8);
const state = ref<'idle' | 'loading' | 'ready' | 'playing' | 'paused'>('idle');
const position = ref(0); // seconds of recording time
const error = ref<string | null>(null);

let ctx: AudioContext | null = null;
let gain: GainNode | null = null;
let source: AudioBufferSourceNode | null = null;
let buffer: AudioBuffer | null = null;
let samples: Float32Array | null = null;
let startedAt = 0;
let startPos = 0;
let raf = 0;

const speed = computed(() => (props.fs && playbackFreq.value ? playbackFreq.value / props.fs : 1));
const channelOptions = computed(() => (['n', 'e', 'z'] as ComponentKey[]).map((c) => ({ value: c, label: props.channels?.[c] ?? c.toUpperCase() })));

function ensureContext(): AudioContext {
    if (!ctx) {
        ctx = new AudioContext();
        gain = ctx.createGain();
        gain.gain.value = volume.value;
        gain.connect(ctx.destination);
    }
    return ctx;
}
watch(volume, (v) => { if (gain) gain.gain.value = v; });

async function load(): Promise<boolean> {
    state.value = 'loading';
    error.value = null;
    try {
        const res = await api.recordings.samples(props.recordingId, { component: channel.value, run: props.runId });
        const v = Float32Array.from(res.values);
        let mean = 0;
        for (const x of v) mean += x;
        mean /= Math.max(1, v.length);
        let peak = 0;
        for (let i = 0; i < v.length; i++) { v[i] -= mean; const a = Math.abs(v[i]); if (a > peak) peak = a; }
        if (peak > 0) for (let i = 0; i < v.length; i++) v[i] /= peak;
        samples = v;
        buffer = null;
        state.value = 'ready';
        return true;
    } catch (e) {
        error.value = (e as Error).message;
        state.value = 'idle';
        toast.error('Could not load samples for playback', (e as Error).message);
        return false;
    }
}

/** Re-clock the samples at the playback frequency by linear interpolation onto the audio context rate. */
function buildBuffer(): AudioBuffer | null {
    if (!samples || !playbackFreq.value) return null;
    const c = ensureContext();
    const rate = c.sampleRate;
    const factor = rate / playbackFreq.value; // output samples per input sample
    const n = samples.length;
    const outLen = Math.max(1, Math.floor(n * factor));
    if (outLen > 60_000_000) { toast.error('Playback too long', 'Increase the playback frequency or select a shorter range.'); return null; }
    const buf = c.createBuffer(1, outLen, rate);
    const out = buf.getChannelData(0);
    for (let i = 0; i < outLen; i++) {
        const x = i / factor;
        const k = Math.floor(x);
        const f = x - k;
        const a = samples[Math.min(k, n - 1)] ?? 0;
        const b = samples[Math.min(k + 1, n - 1)] ?? a;
        out[i] = a + (b - a) * f;
    }
    return buf;
}

function tick() {
    if (state.value !== 'playing' || !ctx) return;
    const t = startPos + (ctx.currentTime - startedAt) * speed.value;
    const dur = props.duration ?? Infinity;
    if (t >= dur) { stop(); return; }
    position.value = t;
    emit('time', t);
    raf = requestAnimationFrame(tick);
}

async function play() {
    if (state.value === 'playing') return;
    if (!samples && !(await load())) return;
    const c = ensureContext();
    if (c.state === 'suspended') await c.resume();
    if (!buffer) buffer = buildBuffer();
    if (!buffer || !gain || !props.fs) return;
    source = c.createBufferSource();
    source.buffer = buffer;
    source.connect(gain);
    const offsetSec = (position.value * props.fs) / (playbackFreq.value ?? 1000);
    source.start(0, Math.max(0, Math.min(offsetSec, buffer.duration - 0.01)));
    startedAt = c.currentTime;
    startPos = position.value;
    state.value = 'playing';
    raf = requestAnimationFrame(tick);
}
function pause() {
    if (state.value !== 'playing') return;
    cancelAnimationFrame(raf);
    try { source?.stop(); } catch { /* already stopped */ }
    source = null;
    state.value = 'paused';
}
function stop() {
    pause();
    position.value = 0;
    state.value = samples ? 'ready' : 'idle';
    emit('time', null);
}
function seek(delta: number) {
    const dur = props.duration ?? 0;
    const wasPlaying = state.value === 'playing';
    pause();
    position.value = Math.max(0, Math.min(dur, position.value + delta));
    emit('time', position.value);
    if (wasPlaying) void play();
}
function bookmark() { emit('bookmark', position.value); }
function onKey(e: KeyboardEvent) {
    if (e.key.toLowerCase() === 'b' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) bookmark();
}
window.addEventListener('keydown', onKey);
watch([channel, () => props.runId], () => { const p = state.value === 'playing'; pause(); samples = null; buffer = null; state.value = 'idle'; if (p) void play(); });
watch(playbackFreq, () => { const p = state.value === 'playing'; pause(); buffer = null; if (p) void play(); });
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); pause(); void ctx?.close(); });
</script>

<template>
    <div class="card p-3 space-y-2.5 text-[12.5px]">
        <div class="flex items-center justify-between gap-2">
            <h3 class="section-title flex items-center gap-1.5 whitespace-nowrap"><Volume2 class="size-4 text-brand-600" /> Seismogram player</h3>
            <span class="num text-faint text-[11px] whitespace-nowrap">{{ fmtDuration(position) }} / {{ fmtDuration(duration) }} · {{ speed.toFixed(1) }}×</span>
        </div>
        <div class="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-x-2 gap-y-2">
            <label class="text-muted">Channel</label>
            <select v-model="channel" class="input"><option v-for="o in channelOptions" :key="o.value" :value="o.value">{{ o.label }}</option></select>
            <label class="text-muted whitespace-nowrap">Playback frequency</label>
            <NumberInput v-model="playbackFreq" :min="100" :max="48000" :step="100" unit="Hz" />
        </div>
        <div class="flex items-center gap-1.5 flex-wrap">
            <Button size="sm" variant="primary" :loading="state === 'loading'" :title="state === 'playing' ? 'Pause' : 'Play'" @click="state === 'playing' ? pause() : play()"><component :is="state === 'playing' ? Pause : Play" class="size-4" /></Button>
            <Button size="sm" icon title="Rewind 30 s" :disabled="state === 'idle' || state === 'loading'" @click="seek(-30)"><Rewind class="size-4" /></Button>
            <Button size="sm" icon title="Forward 30 s" :disabled="state === 'idle' || state === 'loading'" @click="seek(30)"><FastForward class="size-4" /></Button>
            <Button size="sm" icon title="Stop" :disabled="state === 'idle' || state === 'loading'" @click="stop"><Square class="size-4" /></Button>
            <Button size="sm" title="Mark the current position as a transient (key B)" :disabled="state === 'idle' || state === 'loading'" @click="bookmark"><Bookmark class="size-3.5" /> Bookmark</Button>
            <label class="ml-auto flex items-center gap-1.5 text-muted" title="Volume"><Volume2 class="size-3.5" /><input v-model.number="volume" type="range" min="0" max="1" step="0.05" class="w-24 accent-brand-500" /></label>
        </div>
        <p v-if="error" class="text-bad-500 text-[11.5px]">{{ error }}</p>
        <p v-else class="help">Listen for anthropogenic transients (steps, traffic, machinery); bookmark them, then reject the windows that contain bookmarks.</p>
    </div>
</template>
