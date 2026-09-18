<script setup lang="ts">
import { computed, markRaw, onMounted, reactive, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Trash2, ArrowRight } from 'lucide-vue-next';
import PageHeader from '@/components/PageHeader.vue';
import { api } from '@/api';
import type { DisplayData, ProcessingRun, Recording, Step, StepWarning, ComponentKey } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useJobsStore } from '@/stores/jobs';
import { useToastStore } from '@/stores/toast';
import { useUnits } from '@/composables/useUnits';
import { useProcessingPanel, type PanelContent } from '@/composables/usePanel';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Select from '@/components/ui/Select.vue';
import StatusDot from '@/components/ui/StatusDot.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import WaveformPlot from '@/components/plots/WaveformPlot.vue';
import WaveformToolbox from './waveforms/WaveformToolbox.vue';
import SpectraTabs from './waveforms/SpectraTabs.vue';
import SeismogramPlayer from '@/components/SeismogramPlayer.vue';
import type { WaveformController } from './waveforms/controller';
import { fmtDuration, fmtHz, fmtUtc } from '@/utils/format';
import { describeStep, stepDef } from '@/components/processing/defaults';

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const jobs = useJobsStore();
const toast = useToastStore();

const rid = computed(() => String(route.params.r));
const recording = ref<Recording | null>(null);
const error = ref<unknown>(null);
const runId = ref<string | null>(typeof route.query.run === 'string' ? route.query.run : null);
const runs = computed<ProcessingRun[]>(() => recording.value?.runs ?? []);
const currentRun = computed(() => runs.value.find((r) => r.id === runId.value) ?? null);
const channels = computed<Partial<Record<ComponentKey, string>> | undefined>(() => recording.value?.meta?.channels);
const storedUnits = computed(() => currentRun.value?.meta?.units ?? recording.value?.units ?? 'counts');
const unitKind = computed(() => currentRun.value?.meta?.unit_kind ?? recording.value?.unit_kind ?? 'raw');
const unitsUi = useUnits();
const amplitude = computed(() => unitsUi.amplitude(unitKind.value, storedUnits.value));
const units = computed(() => amplitude.value.label);
const rawDisplay = computed(() => unitsUi.convertDisplay(raw.value, unitKind.value, storedUnits.value));
const processedDisplay = computed(() => unitsUi.convertDisplay(processed.value, unitKind.value, storedUnits.value));

const raw = shallowRef<DisplayData | null>(null);
const processed = shallowRef<DisplayData | null>(null);
const loading = ref(false);
const range = ref<[number, number] | null>(null);
const showRaw = ref(true);
const showProcessed = ref(true);
const MAX_POINTS = 4000;
const cursor = ref<number | null>(null);
const cursorShapes = computed(() => (cursor.value === null ? [] : [{ type: 'line' as const, xref: 'x' as const, yref: 'paper' as const, x0: cursor.value, x1: cursor.value, y0: 0, y1: 1, line: { color: '#F26522', width: 2 } }]));
function onBookmark(t: number) { try { const key = `hvsr-bookmarks:${rid.value}`; const list = JSON.parse(localStorage.getItem(key) ?? '[]') as number[]; list.push(Number(t.toFixed(2))); localStorage.setItem(key, JSON.stringify(list.sort((a, b) => a - b))); toast.info(`Bookmark at ${t.toFixed(2)} s`, 'Bookmarks are used on the Windows page.'); } catch { /* ignore */ } }

async function loadRecording() {
    try {
        recording.value = await store.ensureForRecording(rid.value);
        recording.value = store.recording(rid.value) ?? recording.value;
        await loadData();
    } catch (e) { error.value = e; }
}

async function loadData() {
    if (!recording.value) return;
    loading.value = true;
    try {
        const p = { t_start: range.value?.[0] ?? null, t_end: range.value?.[1] ?? null, max_points: MAX_POINTS };
        raw.value = await api.recordings.data(rid.value, { ...p, run: null });
        if (currentRun.value && currentRun.value.status === 'done') {
            processed.value = await api.recordings.data(rid.value, { ...p, run: currentRun.value.id });
        } else if (ctl.steps.some((s) => s.enabled) && ctl.autoPreview) {
            await ctl.preview();
        } else if (!ctl.steps.some((s) => s.enabled)) processed.value = null;
    } catch (e) { error.value = e; } finally { loading.value = false; }
}

// --- processing controller shared with the panel ---
let previewTimer: number | null = null;
const ctl: WaveformController = reactive<WaveformController>({
    steps: [] as Step[],
    warnings: [] as StepWarning[],
    fs: null,
    duration: null,
    previewing: false,
    autoPreview: true,
    onChange() {
        if (previewTimer) window.clearTimeout(previewTimer);
        if (!ctl.autoPreview) return;
        previewTimer = window.setTimeout(() => void ctl.preview(), 500);
    },
    async preview() {
        if (!recording.value) return;
        if (!ctl.steps.some((s) => s.enabled)) { processed.value = null; ctl.warnings = []; return; }
        ctl.previewing = true;
        try {
            const res = await api.recordings.preview(rid.value, { steps: JSON.parse(JSON.stringify(ctl.steps)), t_start: range.value?.[0] ?? null, t_end: range.value?.[1] ?? null, max_points: MAX_POINTS, run_id: null });
            processed.value = res.processed;
            ctl.warnings = res.warnings ?? [];
            runId.value = null;
        } catch (e) {
            toast.error('Preview failed', (e as Error).message);
        } finally { ctl.previewing = false; }
    },
    async run(name: string) {
        if (!recording.value) return;
        try {
            const { run, job } = await api.recordings.createRun(rid.value, { name, steps: JSON.parse(JSON.stringify(ctl.steps.filter((s) => s.enabled))) });
            toast.info('Processing run started', run.name);
            jobs.track({
                key: `run:${run.id}`, label: `Processing · ${run.name}`, kind: 'run', status: job?.status ?? 'queued', progress: job?.progress ?? 0,
                poll: async () => { const r = await api.runs.get(run.id); return { status: r.status, progress: r.progress ?? r.job?.progress ?? 0, message: r.job?.message, error: r.error }; },
                onDone: async (s) => {
                    await store.refresh();
                    recording.value = store.recording(rid.value) ?? recording.value;
                    if (s === 'done') { toast.success('Processing run saved', run.name); runId.value = run.id; await loadData(); }
                    else toast.error('Processing run failed', store.runs.find((x) => x.id === run.id)?.error ?? s);
                },
            });
            await store.refresh();
            recording.value = store.recording(rid.value) ?? recording.value;
        } catch (e) { toast.error('Could not start run', (e as Error).message); }
    },
    reset() { ctl.steps.splice(0); ctl.warnings = []; processed.value = null; },
    suggestRunName() { return `Run ${runs.value.length + 1}: ${ctl.steps.filter((s) => s.enabled).map((s) => stepDef(s.op).label).join(', ').slice(0, 60)}`; },
});

watch(recording, (r) => { ctl.fs = r?.sample_rate ?? r?.meta?.fs ?? null; ctl.duration = r?.duration_s ?? null; }, { immediate: true });

const panelContent = computed<PanelContent | null>(() => ({ title: 'Processing toolbox', component: markRaw(WaveformToolbox), props: { ctl } }));
useProcessingPanel(panelContent);

function onRange(r: [number, number] | null) {
    range.value = r;
    void loadData();
}
async function selectRun(id: string | number | null) {
    runId.value = id ? String(id) : null;
    await router.replace({ query: id ? { run: String(id) } : {} });
    if (currentRun.value) { ctl.steps.splice(0, ctl.steps.length, ...JSON.parse(JSON.stringify(currentRun.value.steps ?? []))); ctl.warnings = currentRun.value.warnings ?? []; }
    await loadData();
}
async function deleteRun(id: string) {
    try { await api.runs.remove(id); await store.refresh(); recording.value = store.recording(rid.value) ?? recording.value; if (runId.value === id) await selectRun(null); toast.success('Run deleted'); } catch (e) { toast.error('Could not delete run', (e as Error).message); }
}
const runOptions = computed(() => [{ value: null, label: 'Raw recording' }, ...runs.value.map((r) => ({ value: r.id, label: `${r.name} (${r.status})`, disabled: r.status !== 'done' }))]);
const downsampleNote = computed(() => (raw.value?.downsampled ? `Displayed at reduced resolution (${raw.value.n_display.toLocaleString()} of ${raw.value.n_samples.toLocaleString()} samples, min/max envelope). Analyses always use the full-resolution data.` : null));

onMounted(async () => {
    await loadRecording();
    if (runId.value && currentRun.value) await selectRun(runId.value);
});
</script>

<template>
    <div class="p-6 space-y-5">
        <ErrorBanner v-if="error" :error="error" @retry="loadRecording" />
        <template v-if="recording">
            <PageHeader :title="recording.name" steps>
                <template #title>{{ recording.name }} <Badge v-if="recording.is_synthetic" tone="accent">synthetic</Badge></template>
                <template #subtitle><span class="num">{{ fmtHz(recording.sample_rate) }} · {{ fmtDuration(recording.duration_s) }} · {{ recording.n_samples?.toLocaleString() }} samples · start {{ fmtUtc(recording.start_time) }} · {{ units }}<span v-if="amplitude.converted" class="text-faint"> (stored as {{ storedUnits }})</span></span></template>
                <template #actions>
                    <label class="flex items-center gap-2 text-[12px] text-muted"><span>Show</span><span class="w-56"><Select :model-value="runId" :options="runOptions" @update:model-value="selectRun" /></span></label>
                    <Button variant="primary" title="Continue with window selection" @click="router.push(`/recordings/${rid}/windows${runId ? `?run=${runId}` : ''}`)">Next: Windows <ArrowRight class="size-4" /></Button>
                </template>
            </PageHeader>

            <Panel title="Three-component waveforms" :subtitle="downsampleNote ?? undefined" :padded="false">
                <template #actions>
                    <Toggle v-model="showRaw" label="Raw" small />
                    <Toggle v-model="showProcessed" label="Processed" small :disabled="!processed" />
                </template>
                <div class="p-2">
                    <WaveformPlot :raw="rawDisplay" :processed="processedDisplay" :show-raw="showRaw" :show-processed="showProcessed" :units="units" :channels="channels" :shapes="cursorShapes" :loading="loading || ctl.previewing" :height="440" @range="onRange" />
                </div>
                <div v-if="processed" class="px-3 pb-2 text-[11.5px] text-muted">Processed overlay: {{ currentRun ? `saved run “${currentRun.name}”` : 'live preview of the toolbox steps' }}<span v-if="processed.fs !== raw?.fs"> · output rate {{ processed.fs }} Hz</span>.</div>
            </Panel>

            <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
                <Panel title="Spectral views">
                    <SpectraTabs :recording-id="rid" :run-id="currentRun?.status === 'done' ? currentRun.id : null" :fs="currentRun?.meta?.fs ?? recording.sample_rate ?? null" :channels="channels" :units="storedUnits" :unit-kind="unitKind" />
                </Panel>
                <div class="space-y-4">
                <SeismogramPlayer :recording-id="rid" :run-id="currentRun?.status === 'done' ? currentRun.id : null" :fs="currentRun?.meta?.fs ?? recording.sample_rate ?? null" :duration="recording.duration_s ?? null" :channels="channels" @time="cursor = $event" @bookmark="onBookmark" />
                <Panel title="Processing runs" :padded="false">
                    <p v-if="runs.length === 0" class="p-3 text-faint text-[12.5px]">No saved runs. Configure steps in the toolbox and use “Run & save”.</p>
                    <ul v-else class="py-1">
                        <li v-for="r in runs" :key="r.id" class="mx-2 my-1 px-3 py-2 rounded-lg text-[12.5px] transition" :class="r.id === runId ? 'bg-brand-500/10' : 'hover:bg-surface-2'">
                            <div class="flex items-center gap-2">
                                <StatusDot :status="r.status" />
                                <button class="font-medium truncate flex-1 text-left" :disabled="r.status !== 'done'" :title="r.status === 'done' ? 'Show this run' : r.status" @click="selectRun(r.id)">{{ r.name }}</button>
                                <Button icon size="xs" variant="ghost" title="Delete run" @click="deleteRun(r.id)"><Trash2 class="size-3.5" /></Button>
                            </div>
                            <ol class="mt-1 text-[11.5px] text-muted num space-y-0.5">
                                <li v-for="(s, i) in r.steps" :key="i">{{ i + 1 }}. {{ stepDef(s.op).label }} {{ describeStep(s) }}</li>
                            </ol>
                            <p v-if="r.error" class="text-bad-500 text-[11.5px] mt-1">{{ r.error }}</p>
                            <p v-if="r.warnings?.length" class="text-warn-500 text-[11.5px] mt-1">{{ r.warnings.length }} warning(s)</p>
                        </li>
                    </ul>
                </Panel>
                </div>
            </div>
            <div class="flex justify-end pt-1">
                <Button variant="primary" size="lg" @click="router.push(`/recordings/${rid}/windows${runId ? `?run=${runId}` : ''}`)">Next step: Window selection <ArrowRight class="size-4" /></Button>
            </div>
        </template>
    </div>
</template>
