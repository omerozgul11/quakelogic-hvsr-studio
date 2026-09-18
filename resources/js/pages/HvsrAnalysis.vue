<script setup lang="ts">
import { computed, markRaw, onMounted, reactive, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter, RouterLink } from 'vue-router';
import { Download, RefreshCw, FileText, Trash2, BarChart3, Grid2x2, Play, Upload, ClipboardList } from 'lucide-vue-next';
import PageHeader from '@/components/PageHeader.vue';
import { api } from '@/api';
import type { Analysis, CurveSet, HvsrResult, Recording, WindowCurves, WindowOverrides, ExportKind, FigureKind, ImportedCurve, Survey, GroundModel } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useJobsStore } from '@/stores/jobs';
import { useToastStore } from '@/stores/toast';
import { useProcessingPanel, type PanelContent } from '@/composables/usePanel';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Tabs from '@/components/ui/Tabs.vue';
import Dropdown from '@/components/ui/Dropdown.vue';
import MenuItem from '@/components/ui/MenuItem.vue';
import Modal from '@/components/ui/Modal.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import StatusDot from '@/components/ui/StatusDot.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import HvsrPlot from '@/components/plots/HvsrPlot.vue';
import { defaultHvsrPlotOptions } from '@/components/plots/hvsrPlotOptions';
import HvTimePlot from '@/components/plots/HvTimePlot.vue';
import SesameBoxes from './hvsr/SesameBoxes.vue';
import ModellingTab from './hvsr/ModellingTab.vue';
import SurveyDialog from '@/components/SurveyDialog.vue';
import { windowColorFor } from '@/utils/windowPalette';
import SpectraPlot from '@/components/plots/SpectraPlot.vue';
import PeakDistributionPlot from '@/components/plots/PeakDistributionPlot.vue';
import AzimuthHeatmap from '@/components/plots/AzimuthHeatmap.vue';
import HvsrPanel, { type HvsrController } from './hvsr/HvsrPanel.vue';
import SesamePanel from './hvsr/SesamePanel.vue';
import { defaultHvsrParams, mergeHvsrParams, validateHvsrParams } from '@/components/processing/defaults';
import { loadDraft } from './hvsr/draft';
import { BRAND } from '@/utils/plotTheme';
import { fmtNum, fmtHz, fmtDate, fmtDuration } from '@/utils/format';

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const jobs = useJobsStore();
const toast = useToastStore();

const analysisId = computed(() => (typeof route.params.a === 'string' ? route.params.a : null));
const analysis = ref<Analysis | null>(null);
const recording = ref<Recording | null>(null);
const result = shallowRef<HvsrResult | null>(null);
const windowCurves = shallowRef<WindowCurves | null>(null);
const error = ref<unknown>(null);
const loading = ref(true);
const overrides = ref<WindowOverrides>({});

const rid = computed(() => (typeof route.params.r === 'string' ? route.params.r : analysis.value?.recording_id ?? null));

// ---- controller for the parameter panel ----
const ctl = reactive<HvsrController>({
    params: defaultHvsrParams(),
    name: '',
    seed: null,
    fs: null,
    duration: null,
    runId: typeof route.query.run === 'string' ? route.query.run : null,
    runOptions: [],
    overridesCount: 0,
    errors: [],
    running: false,
    async run() {
        if (!rid.value) return;
        ctl.running = true;
        try {
            const a = await api.recordings.createAnalysis(rid.value, {
                name: ctl.name.trim(), run_id: ctl.runId, params: JSON.parse(JSON.stringify(ctl.params)),
                window_overrides: JSON.parse(JSON.stringify(overrides.value)), manual_peak: null, random_seed: ctl.seed,
            });
            toast.info('Analysis started', a.name);
            trackAnalysis(a);
            await store.refresh();
            await router.push(`/analyses/${a.id}`);
        } catch (e) { toast.error('Could not start analysis', (e as Error).message); } finally { ctl.running = false; }
    },
    setRun(id) { ctl.runId = id; },
});
const currentRun = computed(() => recording.value?.runs?.find((r) => r.id === ctl.runId) ?? null);
watch([recording, currentRun], () => {
    ctl.fs = currentRun.value?.meta?.fs ?? recording.value?.sample_rate ?? null;
    ctl.duration = recording.value?.duration_s ?? null;
    ctl.runOptions = [{ value: null, label: 'Raw recording' }, ...(recording.value?.runs ?? []).map((r) => ({ value: r.id, label: r.name, disabled: r.status !== 'done' }))];
});
watch(() => JSON.stringify(ctl.params), () => { ctl.errors = validateHvsrParams(ctl.params, ctl.fs, ctl.duration); });

const panelContent = computed<PanelContent | null>(() => ({ title: analysisId.value ? 'Re-run with new parameters' : 'HVSR parameters', component: markRaw(HvsrPanel), props: { ctl } }));
useProcessingPanel(panelContent);

function trackAnalysis(a: Analysis) {
    jobs.track({
        key: `analysis:${a.id}`, label: `HVSR · ${a.name}`, kind: 'analysis', status: a.status, progress: a.progress ?? 0,
        poll: async () => { const x = await api.analyses.get(a.id, false); return { status: x.status, progress: x.progress ?? x.job?.progress ?? 0, message: x.job?.message, error: x.error }; },
        onDone: async (s) => {
            await store.refresh();
            if (analysisId.value === a.id) await loadAnalysis();
            if (s === 'done') toast.success('Analysis finished', a.name);
            else if (s === 'failed') toast.error('Analysis failed', store.analysis(a.id)?.error ?? 'see details');
        },
    });
}

async function loadAnalysis() {
    if (!analysisId.value) return;
    const a = await api.analyses.get(analysisId.value, true);
    analysis.value = a;
    result.value = a.result ?? null;
    overrides.value = a.window_overrides ?? {};
    ctl.overridesCount = Object.keys(overrides.value).length;
    if (a.status === 'queued' || a.status === 'running') trackAnalysis(a);
    if (a.status === 'done' && plotOpt.showSingle) await loadWindowCurves();
}
async function loadWindowCurves() {
    if (!analysisId.value || windowCurves.value) return;
    try { windowCurves.value = await api.analyses.windowCurves(analysisId.value); } catch (e) { toast.warning('Window curves unavailable', (e as Error).message); }
}

onMounted(async () => {
    try {
        if (analysisId.value) {
            const a = await store.ensureForAnalysis(analysisId.value);
            recording.value = store.recording(a.recording_id) ?? (await api.recordings.get(a.recording_id));
            await loadAnalysis();
            Object.assign(ctl.params, mergeHvsrParams(a.params));
            ctl.name = `${a.name} (re-run)`;
            ctl.seed = a.random_seed ?? null;
            ctl.runId = a.processing_run_id ?? null;
        } else if (rid.value) {
            recording.value = await store.ensureForRecording(rid.value);
            recording.value = store.recording(rid.value) ?? recording.value;
            const draft = loadDraft(rid.value);
            if (draft) { Object.assign(ctl.params, draft.params); overrides.value = draft.overrides; ctl.overridesCount = Object.keys(draft.overrides).length; if (draft.runId !== undefined && !ctl.runId) ctl.runId = draft.runId; }
            ctl.name = `HVSR ${(recording.value.analyses?.length ?? 0) + 1} — ${recording.value.name}`;
        }
        ctl.errors = validateHvsrParams(ctl.params, ctl.fs, ctl.duration);
    } catch (e) { error.value = e; } finally { loading.value = false; }
});

const shownParams = computed(() => mergeHvsrParams(analysis.value?.params));
const windowsLabel = computed(() => {
    const w = shownParams.value.windows;
    if (w?.mode === 'auto_variable') return `variable windows ${w.min_length_s}–${w.max_length_s} s`;
    if (w?.mode === 'custom') return 'custom windows';
    return `${shownParams.value.window_length_s} s windows`;
});

// ---- result view state ----
const meanMethod = ref<'geometric' | 'arithmetic' | 'median'>('geometric');
watch(result, (r) => { if (r) meanMethod.value = r.curves.selected; });
const showDirectional = ref(false);
const tab = ref('hvsr');
const tabs = computed(() => [
    { key: 'hvsr', label: 'H/V results' },
    { key: 'time', label: 'H/V vs time', disabled: !result.value?.time_frequency, title: result.value?.time_frequency ? '' : 'Re-run the analysis with the current engine to get the time–frequency matrix' },
    { key: 'azimuth', label: 'H/V rotate', disabled: !result.value?.azimuthal, title: result.value?.azimuthal ? '' : 'Enable Azimuthal H/V in the parameters' },
    { key: 'spectra', label: 'Component spectra' },
    { key: 'peaks', label: 'Peak distribution' },
    { key: 'windows', label: 'Windows' },
    { key: 'sesame', label: 'SESAME', disabled: !result.value?.sesame },
    { key: 'model', label: 'Modelling' },
]);

// ---- GeoExplorer-style plot options ----
const plotOpt = reactive(defaultHvsrPlotOptions());
watch(() => plotOpt.showSingle, (v) => { if (v) void loadWindowCurves(); });
const scale = reactive<{ freqOn: boolean; fmin: number | null; fmax: number | null; ratioOn: boolean; rmin: number | null; rmax: number | null; dbOn: boolean; dmin: number | null; dmax: number | null }>({ freqOn: false, fmin: 0.2, fmax: 50, ratioOn: false, rmin: 0, rmax: 10, dbOn: false, dmin: -50, dmax: 50 });
watch(scale, (sc) => {
    plotOpt.freqRange = sc.freqOn && sc.fmin && sc.fmax && sc.fmax > sc.fmin ? [sc.fmin, sc.fmax] : null;
    plotOpt.ratioRange = sc.ratioOn && sc.rmin !== null && sc.rmax && sc.rmax > sc.rmin ? [sc.rmin, sc.rmax] : null;
    plotOpt.dbRange = sc.dbOn && sc.dmin !== null && sc.dmax !== null && sc.dmax > sc.dmin ? [sc.dmin, sc.dmax] : null;
}, { deep: true });
const loadedCurves = ref<ImportedCurve[]>([]);
const curveInput = ref<HTMLInputElement | null>(null);
async function loadCurveFile(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    (ev.target as HTMLInputElement).value = '';
    if (!f || !store.current) return;
    try { const c = await api.projects.importCurve(store.current.id, f); loadedCurves.value = [...loadedCurves.value, { ...c, name: c.name || f.name }]; plotOpt.showLoaded = true; toast.success('Curve loaded', c.name || f.name); }
    catch (e) { toast.error('Could not load the curve', (e as Error).message); }
}
const heat = reactive({ maxPercent: 100, manualOn: false, manualMax: 10 as number | null });

// ---- window table (use / select) and re-run with edited windows ----
const use = reactive<Record<number, boolean>>({});
const selectedSet = ref<Set<number>>(new Set());
watch(result, (r) => { for (const k of Object.keys(use)) delete use[Number(k)]; if (r) for (const w of r.windows.items) use[w.index] = w.accepted; selectedSet.value = new Set(); });
const windowsDirty = computed(() => !!result.value && result.value.windows.items.some((w) => use[w.index] !== w.accepted));
function setUse(idx: number, v: boolean) { use[idx] = v; }
function selectAllWin() { result.value?.windows.items.forEach((w) => (use[w.index] = true)); }
function invertWin() { result.value?.windows.items.forEach((w) => (use[w.index] = !use[w.index])); }
function clearWin() { result.value?.windows.items.forEach((w) => (use[w.index] = false)); }
function onSelectWindows(idx: number[]) { selectedSet.value = new Set(idx); }
function applySelected(v: boolean) { for (const i of selectedSet.value) use[i] = v; selectedSet.value = new Set(); }
const rerunning = ref(false);
async function rerunWithWindows() {
    if (!analysis.value || !result.value || !rid.value) return;
    rerunning.value = true;
    try {
        const ov: WindowOverrides = { ...(analysis.value.window_overrides ?? {}) };
        for (const w of result.value.windows.items) if (use[w.index] !== w.accepted) ov[String(w.index)] = { accepted: use[w.index], reason: 'manual' };
        const a = await api.recordings.createAnalysis(rid.value, { name: `${analysis.value.name} (windows edited)`, run_id: analysis.value.processing_run_id ?? null, params: JSON.parse(JSON.stringify(mergeHvsrParams(analysis.value.params))), window_overrides: ov, manual_peak: null, random_seed: analysis.value.random_seed ?? null });
        trackAnalysis(a);
        await store.refresh();
        toast.info('Analysis started with the edited window set', a.name);
        await router.push(`/analyses/${a.id}`);
    } catch (e) { toast.error('Could not start the analysis', (e as Error).message); } finally { rerunning.value = false; }
}

// ---- survey / report details ----
const surveyOpen = ref(false);
const survey = computed<Survey | null>(() => analysis.value?.survey ?? null);
function onSurveySaved(sv: Survey) { if (analysis.value) analysis.value = { ...analysis.value, survey: sv }; }
const models = computed<GroundModel[]>(() => analysis.value?.models ?? []);
function onModelsChanged(m: GroundModel[]) { if (analysis.value) analysis.value = { ...analysis.value, models: m }; }

const curve = computed<CurveSet | null>(() => (result.value ? result.value.curves[meanMethod.value] : null));
const curveLabel = computed(() => ({ geometric: 'Geometric (log) mean H/V', arithmetic: 'Arithmetic mean H/V', median: 'Median H/V' }[meanMethod.value]));
const directionalExtra = computed(() => {
    if (!result.value?.directional || !showDirectional.value) return [];
    return [
        { label: '|N|/|Z|', values: result.value.directional.n_over_z.values, color: BRAND.n, dash: 'dash' as const },
        { label: '|E|/|Z|', values: result.value.directional.e_over_z.values, color: BRAND.e, dash: 'dash' as const },
    ];
});
const peakTone = computed(() => ({ clear: 'ok', multiple: 'warn', none: 'neutral', insufficient_data: 'bad' } as const)[result.value?.peaks.status ?? 'none']);

// ---- peak selection ----
const manualFreq = ref<number | null>(null);
const selecting = ref(false);
async function selectPeak(freq: number | null) {
    if (!analysisId.value) return;
    selecting.value = true;
    try {
        const a = await api.analyses.selectPeak(analysisId.value, freq);
        analysis.value = a;
        result.value = a.result ?? (await api.analyses.get(analysisId.value, true)).result ?? result.value;
        toast.success(freq === null ? 'Automatic peak restored' : `Peak selected at ${fmtNum(freq, 4)} Hz`);
        await store.refresh();
    } catch (e) { toast.error('Could not select peak', (e as Error).message); } finally { selecting.value = false; }
}

// ---- exports / report ----
async function exportKind(kind: ExportKind) {
    if (!analysisId.value) return;
    try { await api.analyses.download(analysisId.value, kind); } catch (e) { toast.error('Export failed', (e as Error).message); }
}
async function figure(fig: FigureKind, fmt: 'png' | 'svg' | 'pdf') {
    if (!analysisId.value) return;
    try { await api.analyses.figure(analysisId.value, fig, fmt); } catch (e) { toast.error('Figure export failed', (e as Error).message); }
}
const figExports = (fig: FigureKind) => [{ label: 'PDF (via engine)', action: () => figure(fig, 'pdf') }, { label: 'PNG (via engine)', action: () => figure(fig, 'png') }, { label: 'SVG (via engine)', action: () => figure(fig, 'svg') }];

const reportBusy = computed(() => analysis.value?.report_status === 'queued' || analysis.value?.report_status === 'running' || jobs.isActive(`report:${analysisId.value}`));
async function generateReport() {
    if (!analysisId.value) return;
    const id = analysisId.value;
    try {
        const res = await api.analyses.requestReport(id);
        if (res.analysis) analysis.value = res.analysis;
        toast.info('Report generation started');
        jobs.track({
            key: `report:${id}`, label: 'PDF report', kind: 'report', status: 'queued', progress: 0,
            poll: async () => { const x = await api.analyses.get(id, false); analysis.value = { ...x, result: analysis.value?.result ?? null }; return { status: x.report_status ?? 'running', progress: x.report_status === 'done' ? 1 : 0.5 }; },
            onDone: async (s) => { if (s === 'done') { toast.success('Report ready'); await api.analyses.downloadReport(id); } else toast.error('Report failed'); },
        });
    } catch (e) { toast.error('Could not generate report', (e as Error).message); }
}
async function rerun() {
    if (!analysisId.value) return;
    try { const a = await api.analyses.rerun(analysisId.value); trackAnalysis(a); analysis.value = a; result.value = null; windowCurves.value = null; toast.info('Re-run started with the stored parameters and seed'); } catch (e) { toast.error('Could not re-run', (e as Error).message); }
}
const confirmDelete = ref(false);
async function remove() {
    if (!analysisId.value) return;
    try { await api.analyses.remove(analysisId.value); await store.refresh(); toast.success('Analysis deleted'); await router.push(rid.value ? `/recordings/${rid.value}/hvsr` : '/projects'); } catch (e) { toast.error('Could not delete', (e as Error).message); }
}
const rejected = computed(() => result.value?.windows.items.filter((w) => !w.accepted) ?? []);
const recordingAnalyses = computed(() => recording.value?.analyses ?? []);
</script>

<template>
    <div class="p-6 space-y-5">
        <ErrorBanner v-if="error" :error="error" />
        <p v-else-if="loading" class="text-muted text-[12.5px]">Loading…</p>

        <!-- New analysis mode -->
        <template v-else-if="!analysisId && recording">
            <PageHeader :title="recording.name" subtitle="HVSR analysis · set the parameters in the panel on the right, then run. Every parameter, the accepted windows and the random seed are stored with the result." steps>
                <template #actions>
                    <Button variant="primary" :disabled="ctl.errors.length > 0" :loading="ctl.running" @click="ctl.run()"><Play class="size-4" />Run analysis</Button>
                </template>
            </PageHeader>
            <EmptyState title="Ready to analyse" description="Press Run analysis to compute the H/V curve with the parameters in the panel, or open a previous result below." :icon="BarChart3">
                <Button @click="router.push(`/recordings/${recording.id}/windows${ctl.runId ? `?run=${ctl.runId}` : ''}`)"><Grid2x2 class="size-4" />Review windows first</Button>
                <Button variant="primary" :disabled="ctl.errors.length > 0" :loading="ctl.running" @click="ctl.run()"><Play class="size-4" />Run analysis</Button>
            </EmptyState>
            <Panel v-if="recordingAnalyses.length" title="Previous analyses of this recording" :padded="false">
                <table class="table hover">
                    <thead><tr><th></th><th>Name</th><th>f0</th><th>A0</th><th>Peak</th><th>Windows</th><th>Created</th></tr></thead>
                    <tbody>
                        <tr v-for="a in recordingAnalyses" :key="a.id">
                            <td><StatusDot :status="a.status" /></td>
                            <td><RouterLink :to="`/analyses/${a.id}`" class="font-medium hover:underline">{{ a.name }}</RouterLink></td>
                            <td class="num">{{ fmtHz(a.summary?.f0) }}</td>
                            <td class="num">{{ fmtNum(a.summary?.a0) }}</td>
                            <td><Badge>{{ a.summary?.peak_status ?? a.status }}</Badge></td>
                            <td class="num">{{ a.summary?.count_accepted ?? '—' }}/{{ a.summary?.count_total ?? '—' }}</td>
                            <td class="text-faint">{{ fmtDate(a.created_at) }}</td>
                        </tr>
                    </tbody>
                </table>
            </Panel>
        </template>

        <!-- Existing analysis -->
        <template v-else-if="analysis">
            <PageHeader :title="analysis.name" steps>
                <template #title><StatusDot :status="analysis.status" />{{ analysis.name }}</template>
                <template #subtitle>{{ windowsLabel }} · K–O b = {{ shownParams.smoothing.bandwidth }} · H = {{ shownParams.horizontal_method === 'rms' ? 'RMS' : shownParams.horizontal_method.replace('_', ' ') }} · {{ shownParams.mean_method }} statistic</template>
                <template #actions>
                <Button title="Re-run with the stored parameters and seed" @click="rerun"><RefreshCw class="size-3.5" />Re-run</Button>
                <Dropdown label="Export" title="CSV and JSON exports always use the original SI / raw units">
                    <template #icon><Download class="size-3.5" /></template>
                    <MenuItem @click="exportKind('hvsr-csv')">H/V curves (CSV)</MenuItem>
                    <MenuItem @click="exportKind('windows-csv')">Window curves (CSV)</MenuItem>
                    <MenuItem @click="exportKind('spectra-csv')">Component spectra (CSV)</MenuItem>
                    <MenuItem v-if="result?.azimuthal" @click="exportKind('azimuthal-csv')">Azimuthal matrix (CSV)</MenuItem>
                    <MenuItem @click="exportKind('summary-csv')">Summary (CSV)</MenuItem>
                    <MenuItem @click="exportKind('summary-json')">Summary (JSON)</MenuItem>
                    <MenuItem @click="exportKind('config-json')">Processing configuration (JSON)</MenuItem>
                    <MenuItem @click="exportKind('geopsy-hv')">Geopsy .hv curve</MenuItem>
                    <MenuItem @click="exportKind('windows-json')">Window set (JSON)</MenuItem>
                </Dropdown>
                <Button title="Survey, place, photos and notes printed in the report" :disabled="analysis.status !== 'done'" @click="surveyOpen = true"><ClipboardList class="size-3.5" />Report details</Button>
                <Button variant="primary" :loading="reportBusy" :disabled="analysis.status !== 'done'" @click="analysis.report_status === 'done' ? api.analyses.downloadReport(analysis.id) : generateReport()"><FileText class="size-3.5" />{{ analysis.report_status === 'done' ? 'Download report' : 'PDF report' }}</Button>
                <Button v-if="analysis.report_status === 'done'" icon variant="ghost" title="Regenerate the report" @click="generateReport"><RefreshCw class="size-3.5" /></Button>
                <Button icon variant="ghost" title="Delete analysis" @click="confirmDelete = true"><Trash2 class="size-3.5" /></Button>
                </template>
            </PageHeader>

            <Panel v-if="analysis.status === 'queued' || analysis.status === 'running'">
                <div class="flex items-center gap-3 text-[12.5px]"><span class="font-medium">{{ analysis.status === 'queued' ? 'Queued' : 'Running' }}…</span><div class="flex-1"><ProgressBar :value="analysis.progress ?? 0" :indeterminate="analysis.status === 'queued'" /></div></div>
            </Panel>
            <ErrorBanner v-else-if="analysis.status === 'failed'" :error="new Error(analysis.error ?? 'Analysis failed')" title="Analysis failed" />
            <Panel v-else-if="analysis.status === 'cancelled'"><p class="text-[12.5px] text-muted">This analysis was cancelled. Use Re-run to compute it.</p></Panel>

            <template v-if="result && curve">
                <div class="grid grid-cols-2 md:grid-cols-3 2xl:grid-cols-6 gap-3">
                    <div class="card p-4"><div class="eyebrow">Selected f0</div><div class="num text-[18px] font-semibold text-accent-600 dark:text-accent-300">{{ result.peaks.selected ? fmtNum(result.peaks.selected.frequency, 4) : '—' }} <span class="text-[12px] font-normal text-muted">Hz</span></div><div class="text-[11px] text-faint">{{ result.peaks.selected?.source ?? 'no selection' }}</div></div>
                    <div class="card p-4"><div class="eyebrow">Amplitude A0</div><div class="num text-[18px] font-semibold">{{ result.peaks.selected ? fmtNum(result.peaks.selected.amplitude, 3) : '—' }}</div><div class="text-[11px] text-faint">H/V ratio, not site amplification</div></div>
                    <div class="card p-4"><div class="eyebrow">Peak status</div><div class="mt-1"><Badge :tone="peakTone">{{ result.peaks.status.replace('_', ' ') }}</Badge></div><div class="text-[11px] text-faint mt-1 line-clamp-3" :title="result.peaks.message">{{ result.peaks.message }}</div></div>
                    <div class="card p-4"><div class="eyebrow">Windows</div><div class="num text-[18px] font-semibold">{{ result.windows.count_accepted }} <span class="text-[12px] font-normal text-muted">/ {{ result.windows.count_total }}</span></div><div class="text-[11px] text-faint">{{ result.windows.length_s }} s, overlap {{ Math.round(result.windows.overlap * 100) }}%</div></div>
                    <div class="card p-4"><div class="eyebrow whitespace-nowrap">f0 spread (16–84 %)</div><div class="num text-[15px] font-semibold whitespace-nowrap">{{ fmtNum(result.peak_variability.p16, 3) }} – {{ fmtNum(result.peak_variability.p84, 3) }} <span class="text-[12px] font-normal text-muted">Hz</span></div><div class="text-[11px] text-faint">median {{ fmtNum(result.peak_variability.median, 3) }} Hz · n = {{ result.peak_variability.n }}</div></div>
                    <div class="card p-4"><div class="eyebrow">SESAME</div><div v-if="result.sesame" class="mt-1 space-x-1"><Badge :tone="result.sesame.reliability_passed ? 'ok' : 'bad'">reliable {{ result.sesame.reliability_passed ? '✓' : '✗' }}</Badge><Badge :tone="result.sesame.clarity_passed ? 'ok' : 'warn'">clear {{ result.sesame.clarity_passed_count }}/6</Badge></div><div v-else class="text-[12px] text-faint mt-1">not evaluated</div></div>
                </div>

                <div v-if="result.quality_flags.length" class="flex flex-wrap gap-1.5">
                    <Badge v-for="(f, i) in result.quality_flags" :key="i" :tone="f.severity === 'error' ? 'bad' : f.severity === 'warning' ? 'warn' : 'neutral'" :title="f.message">{{ f.code.replace(/_/g, ' ') }}</Badge>
                </div>

                <Tabs v-model="tab" :tabs="tabs">
                    <template #end>
                        <div v-if="tab === 'hvsr'" class="flex items-center gap-3 text-[12px]">
                            <label class="flex items-center gap-1 text-muted">Statistic
                                <select v-model="meanMethod" class="input !w-auto !py-0.5 !h-7"><option value="geometric">Geometric mean</option><option value="arithmetic">Arithmetic mean</option><option value="median">Median</option></select>
                            </label>
                            <Toggle v-if="result.directional" v-model="showDirectional" label="|N|/|Z|, |E|/|Z|" small />
                        </div>
                        <div v-else-if="tab === 'time' || tab === 'azimuth'" class="flex items-center gap-3 text-[12px]">
                            <label class="flex items-center gap-1 text-muted">Use max colour at <span class="w-20"><NumberInput v-model="heat.maxPercent" :min="5" :max="100" :step="5" unit="%" /></span></label>
                            <Toggle v-model="heat.manualOn" label="Colour manual scale" small />
                            <span class="w-24"><NumberInput v-model="heat.manualMax" :min="0.1" :disabled="!heat.manualOn" placeholder="max H/V" /></span>
                        </div>
                    </template>
                </Tabs>

                <template v-if="tab === 'hvsr'">
                    <div class="grid grid-cols-1 xl:grid-cols-[196px_minmax(0,1fr)_auto] gap-4 items-start">
                        <Panel title="Windows" :padded="false" dense>
                            <template #actions><span class="num text-[11px] text-faint">{{ result.windows.count_accepted }}/{{ result.windows.count_total }}</span></template>
                            <div class="overflow-auto max-h-[420px] scroll-thin">
                                <table class="table">
                                    <thead><tr><th></th><th>#</th><th>Len (s)</th><th>Use</th></tr></thead>
                                    <tbody>
                                        <tr v-for="w in result.windows.items" :key="w.index" :class="[use[w.index] ? '' : 'text-muted', selectedSet.has(w.index) ? 'bg-brand-500/10' : '']" @click="selectedSet.has(w.index) ? selectedSet.delete(w.index) : selectedSet.add(w.index); selectedSet = new Set(selectedSet)">
                                            <td><span class="inline-block size-3.5 rounded-sm border border-black/10" :style="{ background: use[w.index] ? windowColorFor(w, result.windows.items.length) : '#9aa0ab' }" /></td>
                                            <td class="num">{{ w.index }}</td>
                                            <td class="num">{{ fmtNum(w.length_s ?? w.end_s - w.start_s, 3) }}</td>
                                            <td @click.stop><input type="checkbox" :checked="use[w.index]" class="accent-brand-500" @change="setUse(w.index, ($event.target as HTMLInputElement).checked)" /></td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                            <div class="p-2 divider flex flex-wrap gap-1">
                                <Button size="xs" @click="selectAllWin">Select all</Button><Button size="xs" @click="invertWin">Invert</Button><Button size="xs" @click="clearWin">Clear</Button>
                                <template v-if="selectedSet.size"><Button size="xs" variant="primary" @click="applySelected(false)">Reject {{ selectedSet.size }}</Button><Button size="xs" @click="applySelected(true)">Accept {{ selectedSet.size }}</Button></template>
                            </div>
                            <div v-if="windowsDirty" class="p-2 divider"><Button class="w-full" size="sm" variant="primary" :loading="rerunning" title="Creates a new analysis with the edited window set (this one is kept)" @click="rerunWithWindows"><Play class="size-3.5" />Re-run with these windows</Button></div>
                        </Panel>
                        <Panel :padded="false">
                            <div class="p-2">
                                <HvsrPlot :frequency="result.frequency" :curve="curve" :curve-label="curveLabel" :window-curves="windowCurves" :candidates="result.peaks.candidates" :selected="result.peaks.selected" :search-range="result.peaks.search_range" :extra="directionalExtra" :loaded="loadedCurves" :spectra="{ h: result.components.h ?? null, z: result.components.z ?? null }" :t10="result.t10_hz ?? (result.windows.length_s ? 10 / result.windows.length_s : null)" :options="plotOpt" :height="460" :extra-exports="figExports('hvsr')" :title="`H/V spectral ratio — ${curveLabel}`" @pick="(f) => (manualFreq = f)" @select-windows="onSelectWindows" />
                            </div>
                            <div class="px-3 pb-3 text-[11.5px] text-muted">
                                Dispersion: <span class="num">{{ curve.band }}</span> (statistical dispersion of the window curves, not a confidence interval).
                                <span v-if="result.masking.invalid_bins.length"> · {{ result.masking.invalid_bins.length }} frequency bins invalid (vertical amplitude below floor in too many windows).</span>
                                <span v-if="plotOpt.selectWindows" class="text-brand-700"> · Drag a box across the single-window curves to select windows.</span>
                            </div>
                            <div class="divider mx-3" />
                            <div class="p-3 grid grid-cols-1 lg:grid-cols-2 gap-x-6 gap-y-2 text-[12px]">
                                <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <Toggle v-model="plotOpt.showMean" label="Show ratio" small />
                                    <label class="flex items-center gap-1 text-muted">Standard deviations <select v-model="plotOpt.stdMode" class="input !w-auto !py-0.5 !h-7"><option value="band">band</option><option value="lines">curves</option><option value="none">off</option></select></label>
                                    <Toggle v-model="plotOpt.showT10" label="T10" small help="Shades frequencies below 10 / window length, where the SESAME reliability criterion is not met." />
                                    <Toggle v-model="plotOpt.showSingle" label="Show single ratios" small />
                                    <Toggle v-model="plotOpt.selectWindows" label="Select windows by box" small :disabled="!plotOpt.showSingle" />
                                </div>
                                <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <Toggle v-model="plotOpt.showLoaded" label="Show loaded H/V curve" small :disabled="!loadedCurves.length" />
                                    <input ref="curveInput" type="file" accept=".hv,.csv,.txt" class="hidden" @change="loadCurveFile" />
                                    <Button size="xs" @click="curveInput?.click()"><Upload class="size-3.5" />Load curve (.hv / .csv)</Button>
                                    <span v-if="loadedCurves.length" class="text-faint">{{ loadedCurves.length }} loaded</span><button v-if="loadedCurves.length" class="underline text-faint" @click="loadedCurves = []">clear</button>
                                </div>
                                <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <span class="text-muted">Absolute averages</span>
                                    <Toggle v-model="plotOpt.dbHorizontal" label="Horizontal (dB)" small />
                                    <Toggle v-model="plotOpt.dbVertical" label="Vertical (dB)" small />
                                    <Toggle v-model="scale.dbOn" label="dB manual scale" small />
                                    <span class="flex gap-1 w-44"><NumberInput v-model="scale.dmin" :disabled="!scale.dbOn" unit="dB" /><NumberInput v-model="scale.dmax" :disabled="!scale.dbOn" unit="dB" /></span>
                                </div>
                                <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                                    <Toggle v-model="scale.freqOn" label="Frequency manual scale" small />
                                    <span class="flex gap-1 w-44"><NumberInput v-model="scale.fmin" :disabled="!scale.freqOn" unit="Hz" /><NumberInput v-model="scale.fmax" :disabled="!scale.freqOn" unit="Hz" /></span>
                                    <Toggle v-model="scale.ratioOn" label="H/V manual scale" small />
                                    <span class="flex gap-1 w-36"><NumberInput v-model="scale.rmin" :disabled="!scale.ratioOn" /><NumberInput v-model="scale.rmax" :disabled="!scale.ratioOn" /></span>
                                    <Toggle :model-value="!plotOpt.freqLog" label="Frequency linear scale" small @update:model-value="plotOpt.freqLog = !$event" />
                                </div>
                            </div>
                        </Panel>
                        <SesameBoxes v-if="result.sesame" :sesame="result.sesame" />
                    </div>
                    <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                        <Panel title="Candidate peaks" :subtitle="`Search range ${fmtNum(result.peaks.search_range[0], 3)}–${fmtNum(result.peaks.search_range[1], 3)} Hz`" :padded="false">
                            <table class="table hover">
                                <thead><tr><th>#</th><th>Frequency</th><th>Amplitude</th><th>Prominence</th><th></th></tr></thead>
                                <tbody>
                                    <tr v-for="c in result.peaks.candidates" :key="c.rank" :class="result.peaks.selected && Math.abs(result.peaks.selected.frequency - c.frequency) < 1e-9 ? 'bg-accent-500/8' : ''">
                                        <td class="num">{{ c.rank }}</td><td class="num">{{ fmtHz(c.frequency) }}</td><td class="num">{{ fmtNum(c.amplitude, 3) }}</td><td class="num">{{ fmtNum(c.prominence, 3) }}</td>
                                        <td><Button size="sm" :loading="selecting" @click="selectPeak(c.frequency)">Select</Button></td>
                                    </tr>
                                    <tr v-if="!result.peaks.candidates.length"><td colspan="5" class="text-faint text-center py-3">No local maxima found in the search range.</td></tr>
                                </tbody>
                            </table>
                            <div class="flex items-center gap-2 p-3 border-t border-ui text-[12.5px]">
                                <span class="text-muted">Manual frequency</span>
                                <div class="w-32"><NumberInput v-model="manualFreq" :min="0" unit="Hz" nullable placeholder="click plot" /></div>
                                <Button size="sm" :disabled="manualFreq === null" :loading="selecting" @click="selectPeak(manualFreq)">Select</Button>
                                <Button size="sm" variant="ghost" :disabled="result.peaks.selected?.source !== 'manual'" @click="selectPeak(null)">Back to automatic</Button>
                            </div>
                        </Panel>
                        <Panel title="Peak-frequency variability" :subtitle="result.peak_variability.definition">
                            <dl class="grid grid-cols-[170px_1fr] gap-y-1 text-[12.5px]">
                                <dt class="text-muted">Windows with a peak</dt><dd class="num">{{ result.peak_variability.n }}</dd>
                                <dt class="text-muted">Median f0</dt><dd class="num">{{ fmtHz(result.peak_variability.median) }}</dd>
                                <dt class="text-muted">16th – 84th percentile</dt><dd class="num">{{ fmtNum(result.peak_variability.p16, 4) }} – {{ fmtNum(result.peak_variability.p84, 4) }} Hz</dd>
                                <dt class="text-muted">Std. dev. σf</dt><dd class="num">{{ fmtNum(result.peak_variability.std, 4) }} Hz (σ ln f0 = {{ fmtNum(result.peak_variability.std_ln, 3) }})</dd>
                                <template v-if="result.peak_variability.bootstrap">
                                    <dt class="text-muted">Bootstrap f0 interval</dt><dd class="num">{{ fmtNum(result.peak_variability.bootstrap.f0_p2_5, 4) }} – {{ fmtNum(result.peak_variability.bootstrap.f0_p97_5, 4) }} Hz <span class="text-faint">(2.5–97.5 %, {{ result.peak_variability.bootstrap.n_resamples }} resamples, seed {{ result.peak_variability.bootstrap.seed }})</span></dd>
                                    <dt class="text-muted">Bootstrap A0 interval</dt><dd class="num">{{ fmtNum(result.peak_variability.bootstrap.a0_p2_5, 3) }} – {{ fmtNum(result.peak_variability.bootstrap.a0_p97_5, 3) }}</dd>
                                </template>
                            </dl>
                            <p v-if="result.peak_variability.bootstrap" class="help">{{ result.peak_variability.bootstrap.definition }}</p>
                        </Panel>
                    </div>
                </template>

                <Panel v-else-if="tab === 'spectra'" :padded="false">
                    <div class="p-2"><SpectraPlot :frequency="result.frequency" :series="result.components" kind="fas" units="counts·s" :channels="recording?.meta?.channels" :height="420" :extra-exports="figExports('spectra')" title="Mean smoothed Fourier amplitude spectra over accepted windows" /></div>
                </Panel>

                <Panel v-else-if="tab === 'peaks'" :padded="false">
                    <div class="p-2"><PeakDistributionPlot :variability="result.peak_variability" :selected="result.peaks.selected?.frequency ?? null" :height="360" :extra-exports="figExports('peak_distribution')" /></div>
                </Panel>

                <Panel v-else-if="tab === 'time' && result.time_frequency" :padded="false">
                    <div class="p-2"><HvTimePlot :times-s="result.time_frequency.times_s" :frequency="result.time_frequency.frequency" :matrix="result.time_frequency.matrix" :start-time="recording?.start_time ?? result.input.start_time" :accepted="result.windows.items.map((w) => use[w.index] ?? w.accepted)" :max-percent="heat.maxPercent" :manual-max="heat.manualOn ? heat.manualMax : null" :height="460" /></div>
                    <p class="px-3 pb-3 text-[11.5px] text-muted">H/V level of every accepted window against its start time: a stationary site response shows a horizontal band at f0; vertical stripes mark windows dominated by transients.</p>
                </Panel>

                <Panel v-else-if="tab === 'azimuth' && result.azimuthal" :padded="false">
                    <div class="p-2"><AzimuthHeatmap :azimuths="result.azimuthal.azimuths" :frequency="result.azimuthal.frequency" :matrix="result.azimuthal.matrix" :peak-frequency="result.azimuthal.peak_frequency" :max-percent="heat.maxPercent" :manual-max="heat.manualOn ? heat.manualMax : null" :height="460" :extra-exports="figExports('azimuthal')" /></div>
                    <p class="px-3 pb-3 text-[11.5px] text-muted">Directional dependence of H/V. Strong azimuthal variation can indicate 2-D/3-D structure or directional noise sources; it is not, by itself, evidence of a resonance.</p>
                </Panel>

                <Panel v-else-if="tab === 'windows'" :padded="false">
                    <div class="p-3 text-[12.5px] flex flex-wrap gap-2 items-center">
                        <Badge tone="ok">{{ result.windows.count_accepted }} accepted</Badge><Badge tone="bad">{{ result.windows.count_rejected }} rejected</Badge>
                        <span class="text-muted">Masking policy: <span class="num">{{ result.masking.policy }}</span></span>
                        <div class="flex-1" />
                        <Button size="sm" @click="figure('windows', 'png')">Window figure (PNG)</Button>
                        <RouterLink v-if="rid" :to="`/recordings/${rid}/windows${analysis.processing_run_id ? `?run=${analysis.processing_run_id}` : ''}`" class="text-[12px] underline text-muted">Edit windows</RouterLink>
                    </div>
                    <div class="overflow-auto max-h-96 scroll-thin">
                        <table class="table hover">
                            <thead><tr><th>#</th><th>Start (s)</th><th>End (s)</th><th>Status</th><th>Reason</th><th>f0 (Hz)</th><th>A0</th><th>STA/LTA max</th></tr></thead>
                            <tbody>
                                <tr v-for="w in result.windows.items" :key="w.index" :class="w.accepted ? '' : 'text-muted'">
                                    <td class="num">{{ w.index }}</td><td class="num">{{ fmtNum(w.start_s, 5) }}</td><td class="num">{{ fmtNum(w.end_s, 5) }}</td>
                                    <td><Badge :tone="w.accepted ? 'ok' : 'bad'">{{ w.accepted ? 'accepted' : 'rejected' }}</Badge></td>
                                    <td class="text-[11.5px]">{{ w.reason ?? '' }}</td><td class="num">{{ fmtNum(w.f0, 4) }}</td><td class="num">{{ fmtNum(w.a0, 3) }}</td><td class="num">{{ fmtNum(w.sta_lta_max) }}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <p v-if="rejected.length" class="px-3 py-2 text-[11.5px] text-faint border-t border-ui">{{ rejected.length }} rejected window(s).</p>
                </Panel>

                <Panel v-else-if="tab === 'sesame' && result.sesame"><SesamePanel :sesame="result.sesame" /></Panel>

                <ModellingTab v-else-if="tab === 'model'" :analysis-id="analysis.id" :frequency="result.frequency" :curve="curve" :models="models" @models-changed="onModelsChanged" />

                <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <Panel title="Interpretation limitations">
                        <ul class="list-disc pl-4 space-y-1 text-[12.5px] text-muted">
                            <li v-for="(n, i) in result.interpretation_notes ?? []" :key="i">{{ n }}</li>
                            <li v-if="!result.interpretation_notes?.length">The H/V amplitude is a spectral ratio, not a direct measurement of site amplification, and no unique velocity profile can be inferred from HVSR alone.</li>
                        </ul>
                    </Panel>
                    <Panel title="Reproducibility">
                        <dl class="grid grid-cols-[150px_1fr] gap-y-1 text-[12.5px]">
                            <dt class="text-muted">Engine version</dt><dd class="num">{{ result.engine_version }}<span v-if="result.versions" class="text-faint"> · numpy {{ result.versions.numpy }}, scipy {{ result.versions.scipy }}, obspy {{ result.versions.obspy }}</span></dd>
                            <dt class="text-muted">Random seed</dt><dd class="num">{{ result.random_seed ?? '—' }}</dd>
                            <dt class="text-muted">Computed</dt><dd class="num">{{ result.computed_at }} ({{ fmtDuration(result.elapsed_s) }})</dd>
                            <dt class="text-muted">Input</dt><dd class="num break-all text-[11.5px]">{{ result.input.path }}<br /><span class="text-faint">sha256 {{ result.input.sha256 }}</span></dd>
                            <dt class="text-muted">Combination</dt><dd>{{ result.params.horizontal_method.replace('_', ' ') }}, {{ result.params.combination_stage.replace('_', ' ') }}</dd>
                            <dt class="text-muted">Result folder</dt><dd class="num break-all text-[11.5px]">{{ analysis.result_dir }}</dd>
                        </dl>
                        <div class="mt-3"><Button size="sm" @click="rerun"><RefreshCw class="size-3.5" />Re-run with identical parameters and seed</Button></div>
                    </Panel>
                </div>
            </template>
        </template>

        <SurveyDialog v-if="analysis" :open="surveyOpen" :analysis-id="analysis.id" :recording="recording" :survey="survey" :generating="reportBusy" @close="surveyOpen = false" @saved="onSurveySaved" @generate="surveyOpen = false; generateReport()" />

        <Modal :open="confirmDelete" title="Delete analysis?" @close="confirmDelete = false">
            <p class="text-[13px]">Delete <strong>{{ analysis?.name }}</strong> and its result files and exports?</p>
            <template #footer><Button @click="confirmDelete = false">Cancel</Button><Button variant="danger" @click="remove">Delete</Button></template>
        </Modal>
    </div>
</template>
