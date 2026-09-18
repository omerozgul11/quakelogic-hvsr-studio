<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, Info, XCircle, ArrowRight, ArrowLeft, Check } from 'lucide-vue-next';
import PageHeader from '@/components/PageHeader.vue';
import { api } from '@/api';
import { ApiError } from '@/api/client';
import type { Upload, ComponentKey, TimeMode, Issue, CreateRecordingRequest, InspectTrace } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import Button from '@/components/ui/Button.vue';
import Panel from '@/components/ui/Panel.vue';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Select from '@/components/ui/Select.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Badge from '@/components/ui/Badge.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import { fmtBytes, fmtNum } from '@/utils/format';

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const toast = useToastStore();
const pid = computed(() => String(route.params.p));

onMounted(() => { void store.open(pid.value); });

const step = ref(1);
const steps = ['Files', 'Preview', 'Mapping', 'Validate & create'];

// ---- Step 1: uploads ----
const uploads = ref<Upload[]>([]);
const uploading = ref(false);
const uploadError = ref<unknown>(null);
const dragOver = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

async function addFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    uploading.value = true;
    uploadError.value = null;
    try {
        const res = await api.projects.upload(pid.value, list);
        uploads.value.push(...res.map((u) => ({ ...u, upload_id: u.upload_id ?? u.id ?? '' })));
        toast.success(`${res.length} file${res.length > 1 ? 's' : ''} staged`);
    } catch (e) { uploadError.value = e; } finally { uploading.value = false; }
}
function onDrop(e: DragEvent) {
    dragOver.value = false;
    if (e.dataTransfer?.files) void addFiles(e.dataTransfer.files);
}
function removeUpload(id: string) {
    uploads.value = uploads.value.filter((u) => u.upload_id !== id);
}
const asciiUploads = computed(() => uploads.value.filter((u) => u.inspect.format === 'ascii'));
const mseedUploads = computed(() => uploads.value.filter((u) => u.inspect.format === 'mseed' || u.inspect.format === 'seismic'));
const isTraceFormat = (f: string | undefined) => f === 'mseed' || f === 'seismic';
const allTraces = computed<{ upload: Upload; trace: InspectTrace }[]>(() => mseedUploads.value.flatMap((u) => (u.inspect.mseed?.traces ?? []).map((trace) => ({ upload: u, trace }))));

// ---- Step 2: per-file ASCII preview settings ----
interface AsciiCfg { delimiter: string; decimal: string; header_rows: number; comment_prefix: string }
const asciiCfg = reactive<Record<string, AsciiCfg>>({});
const previewFile = ref<string | null>(null);
function cfgFor(u: Upload): AsciiCfg {
    if (!asciiCfg[u.upload_id]) {
        const a = u.inspect.ascii;
        asciiCfg[u.upload_id] = { delimiter: a?.delimiter ?? ',', decimal: a?.decimal ?? '.', header_rows: a?.header_rows ?? 0, comment_prefix: a?.comment_prefix ?? '' };
    }
    return asciiCfg[u.upload_id];
}
const delimiterOptions = [{ value: ',', label: 'Comma (,)' }, { value: '\t', label: 'Tab' }, { value: ';', label: 'Semicolon (;)' }, { value: 'whitespace', label: 'Whitespace' }, { value: ' ', label: 'Single space' }, { value: '|', label: 'Pipe (|)' }];

function parsePreview(u: Upload): { rows: string[][]; nCols: number } {
    const cfg = cfgFor(u);
    const lines = (u.inspect.ascii?.preview_lines ?? []).filter((l) => !(cfg.comment_prefix && l.trimStart().startsWith(cfg.comment_prefix)));
    const body = lines.slice(cfg.header_rows);
    const rows = body.slice(0, 15).map((l) => (cfg.delimiter === 'whitespace' ? l.trim().split(/\s+/) : l.split(cfg.delimiter)).map((c) => c.trim()));
    const nCols = rows.reduce((m, r) => Math.max(m, r.length), 0);
    return { rows, nCols };
}
const previewUpload = computed(() => uploads.value.find((u) => u.upload_id === previewFile.value) ?? asciiUploads.value[0] ?? null);
const preview = computed(() => (previewUpload.value && previewUpload.value.inspect.format === 'ascii' ? parsePreview(previewUpload.value) : null));
function columnCount(u: Upload): number { return parsePreview(u).nCols; }

// ---- Step 3: mapping ----
const mode = ref<'single' | 'split'>('single');
const sourceKind = computed<'ascii' | 'mseed' | 'saf' | 'seismic'>(() => (mode.value === 'split' ? 'ascii' : singleFile.value?.inspect.format === 'seismic' ? 'seismic' : singleFile.value?.inspect.format === 'mseed' ? 'mseed' : singleFile.value?.inspect.format === 'saf' ? 'saf' : 'ascii'));
const isTraceKind = computed(() => sourceKind.value === 'mseed' || sourceKind.value === 'seismic');
const singleFileId = ref<string | null>(null);
const singleFile = computed(() => uploads.value.find((u) => u.upload_id === singleFileId.value) ?? null);
const columns = reactive<Record<ComponentKey, number | null>>({ n: null, e: null, z: null });
const splitFiles = reactive<Record<ComponentKey, string | null>>({ n: null, e: null, z: null });
const splitColumns = reactive<Record<ComponentKey, number | null>>({ n: 0, e: 0, z: 0 });
const traces = reactive<Record<ComponentKey, string | null>>({ n: null, e: null, z: null });
const timeMode = ref<TimeMode>('sample_rate');
const sampleRate = ref<number | null>(null);
const timeColumn = ref<number | null>(null);
const datetimeFormat = ref('');
const startTime = ref('');
const units = ref('counts');
const unitKind = ref('raw');
const scaleFactor = ref(1);
const stationId = ref<string | null>(null);
const newStationCode = ref('');
const recName = ref('');
const orientation = ref(0);
const isSynthetic = ref(false);

function autoMap() {
    const u = singleFile.value;
    if (!u) return;
    if (u.inspect.format === 'ascii' && u.inspect.ascii) {
        const cols = u.inspect.ascii.columns;
        const guess = u.inspect.ascii.time_column_guess;
        const find = (re: RegExp) => cols.find((c) => re.test(c.name))?.index ?? null;
        columns.n = find(/(^|[^a-z])(n|ns|north|hhn|bhn|ehn|y)([^a-z]|$)/i);
        columns.e = find(/(^|[^a-z])(e|ew|east|hhe|bhe|ehe|x)([^a-z]|$)/i);
        columns.z = find(/(^|[^a-z])(z|ud|vert|vertical|hhz|bhz|ehz)([^a-z]|$)/i);
        const numeric = cols.filter((c) => c.numeric && c.index !== (guess?.index ?? -1)).map((c) => c.index);
        if (columns.n === null && columns.e === null && columns.z === null && numeric.length >= 3) { [columns.n, columns.e, columns.z] = numeric; }
        if (guess?.index !== null && guess?.index !== undefined && guess.kind) {
            timeMode.value = guess.kind === 'datetime' ? 'datetime_column' : 'seconds_column';
            timeColumn.value = guess.index;
            sampleRate.value = guess.sample_rate_estimate ?? null;
        } else {
            timeMode.value = 'sample_rate';
            sampleRate.value = u.inspect.ascii.sample_rate_hint ?? null;
        }
        if (!recName.value) recName.value = u.name.replace(/\.[^.]+$/, '');
    } else if (u.inspect.format === 'saf') {
        const saf = u.inspect.saf;
        sampleRate.value = saf?.sample_rate ?? null;
        if (!recName.value) recName.value = u.name.replace(/\.[^.]+$/, '');
    } else if (isTraceFormat(u.inspect.format)) {
        const tr = allTraces.value.map((t) => t.trace);
        const pick = (re: RegExp) => tr.find((t) => re.test(t.channel))?.id ?? null;
        traces.n = pick(/[N1]$/i); traces.e = pick(/[E2]$/i); traces.z = pick(/Z$/i);
        if (!recName.value) recName.value = tr[0] ? `${tr[0].station}` : u.name.replace(/\.[^.]+$/, '');
        if (!newStationCode.value && !stationId.value && tr[0]) newStationCode.value = tr[0].station;
        sampleRate.value = tr[0]?.sampling_rate ?? null;
    }
}
function enterMapping() {
    if (!singleFileId.value) singleFileId.value = uploads.value[0]?.upload_id ?? null;
    if (mode.value === 'single') autoMap();
    else if (!recName.value && uploads.value[0]) recName.value = uploads.value[0].name.replace(/_?[NEZ]\.[^.]+$/i, '');
    step.value = 3;
}
const colOptions = (u: Upload | null) => {
    const n = u ? columnCount(u) : 0;
    const names = u?.inspect.ascii?.columns ?? [];
    return Array.from({ length: n }, (_, i) => ({ value: i, label: `Column ${i + 1}${names[i]?.name ? ` (${names[i].name})` : ''}` }));
};
const traceOptions = computed(() => allTraces.value.map((t) => ({ value: t.trace.id, label: `${t.trace.id} · ${t.trace.sampling_rate} Hz · ${t.trace.npts} pts${t.trace.has_gaps ? ' · GAPS' : ''}` })));
const stationOptions = computed(() => [{ value: null, label: '— New station —' }, ...store.stations.map((s) => ({ value: s.id, label: `${s.code}${s.name ? ' · ' + s.name : ''}` }))]);

const mappingErrors = computed<string[]>(() => {
    const errs: string[] = [];
    if (mode.value === 'single') {
        if (!singleFile.value) errs.push('Select the file that contains all three components.');
        else if (sourceKind.value === 'saf') { /* SAF carries its three channels and timing in the header */ }
        else if (isTraceKind.value) {
            (['n', 'e', 'z'] as ComponentKey[]).forEach((c) => { if (!traces[c]) errs.push(`Assign a trace to the ${c.toUpperCase()} component.`); });
            const ids = [traces.n, traces.e, traces.z].filter(Boolean);
            if (new Set(ids).size !== ids.length) errs.push('Each component must use a different trace.');
        } else {
            (['n', 'e', 'z'] as ComponentKey[]).forEach((c) => { if (columns[c] === null) errs.push(`Assign a column to the ${c.toUpperCase()} component.`); });
            const ids = [columns.n, columns.e, columns.z].filter((v) => v !== null);
            if (new Set(ids).size !== ids.length) errs.push('Each component must use a different column.');
        }
    } else {
        (['n', 'e', 'z'] as ComponentKey[]).forEach((c) => { if (!splitFiles[c]) errs.push(`Choose the file for the ${c.toUpperCase()} component.`); });
    }
    if (sourceKind.value === 'ascii') {
        if (timeMode.value === 'sample_rate') {
            if (!sampleRate.value || sampleRate.value <= 0) errs.push('The file has no usable time column: enter the sampling rate in Hz before continuing.');
        } else if (timeColumn.value === null) errs.push('Choose the time column.');
        if (mode.value === 'split' && timeMode.value !== 'sample_rate') errs.push('With three separate files, timing must be given as a sampling rate.');
    }
    if (!recName.value.trim()) errs.push('Enter a recording name.');
    if (!stationId.value && !newStationCode.value.trim()) errs.push('Choose a station or enter a code for a new one (or set the code to "-" to leave unassigned).');
    return errs;
});

// ---- Step 4: create ----
const creating = ref(false);
const createError = ref<unknown>(null);
const validation = ref<{ blocking: boolean; issues: Issue[] } | null>(null);

function buildRequest(stId: string | null, stationCode: string): CreateRecordingRequest {
    const sources: CreateRecordingRequest['import']['sources'] = [];
    let uploadIds: string[] = [];
    let asciiCols: Partial<Record<ComponentKey, number>> = {};
    let cfg: AsciiCfg | null = null;
    if (mode.value === 'single' && singleFile.value) {
        if (isTraceKind.value) {
            uploadIds = mseedUploads.value.map((u) => u.upload_id);
            uploadIds.forEach((id) => sources.push({ upload_id: id, role: 'all' }));
        } else if (sourceKind.value === 'saf') {
            uploadIds = [singleFile.value.upload_id];
            sources.push({ upload_id: singleFile.value.upload_id, role: 'all' });
        } else {
            uploadIds = [singleFile.value.upload_id];
            sources.push({ upload_id: singleFile.value.upload_id, role: 'all' });
            asciiCols = { n: columns.n ?? 0, e: columns.e ?? 0, z: columns.z ?? 0 };
            cfg = cfgFor(singleFile.value);
        }
    } else {
        (['n', 'e', 'z'] as ComponentKey[]).forEach((c) => {
            const id = splitFiles[c]!;
            uploadIds.push(id);
            sources.push({ upload_id: id, role: c });
            asciiCols[c] = splitColumns[c] ?? 0;
        });
        cfg = cfgFor(uploads.value.find((u) => u.upload_id === splitFiles.n)!);
    }
    return {
        name: recName.value.trim(),
        station_id: stId,
        upload_ids: uploadIds,
        import: {
            sources,
            format: sourceKind.value,
            ascii: sourceKind.value === 'ascii' ? {
                delimiter: cfg!.delimiter, decimal: cfg!.decimal, header_rows: cfg!.header_rows, comment_prefix: cfg!.comment_prefix || null,
                columns: asciiCols,
                time: { mode: timeMode.value, sample_rate: sampleRate.value, column: timeMode.value === 'sample_rate' ? null : timeColumn.value, datetime_format: datetimeFormat.value || null },
                start_time: startTime.value ? new Date(startTime.value).toISOString() : null,
                units: units.value, unit_kind: unitKind.value, scale_factor: scaleFactor.value || 1,
            } : undefined,
            mseed: isTraceKind.value ? { n: traces.n, e: traces.e, z: traces.z, merge_policy: 'reject_gaps' } : undefined,
            metadata: { station: stationCode, network: '', location: '', orientation_deg: orientation.value || 0, is_synthetic: isSynthetic.value },
        },
    };
}

async function create() {
    creating.value = true;
    createError.value = null;
    validation.value = null;
    try {
        let stId = stationId.value;
        let code = store.station(stId)?.code ?? newStationCode.value.trim();
        if (!stId && code && code !== '-') {
            const existing = store.stations.find((s) => s.code.toLowerCase() === code.toLowerCase());
            if (existing) stId = existing.id;
            else { const s = await api.stations.create(pid.value, { code, orientation_deg: orientation.value }); stId = s.id; }
        }
        if (code === '-') code = '';
        const rec = await api.projects.createRecording(pid.value, buildRequest(stId, code));
        validation.value = rec.validation ?? null;
        await store.refresh();
        toast.success('Recording imported', rec.name);
        await router.push(`/recordings/${rec.id}/waveforms`);
    } catch (e) {
        if (e instanceof ApiError && e.status === 422 && (e.payload as { validation?: { blocking: boolean; issues: Issue[] } })?.validation) {
            validation.value = (e.payload as { validation: { blocking: boolean; issues: Issue[] } }).validation;
        } else createError.value = e;
    } finally { creating.value = false; }
}
const issuesBySeverity = computed(() => {
    const out: Record<'error' | 'warning' | 'info', Issue[]> = { error: [], warning: [], info: [] };
    for (const i of validation.value?.issues ?? []) out[i.severity].push(i);
    return out;
});
const ISSUE_HELP: Record<string, string> = {
    missing_component: 'One of N, E or Z could not be read. The engine never substitutes a missing component.',
    sample_rate_mismatch: 'Components have different sampling rates. Resampling is never done silently — fix the source files or import separately.',
    length_mismatch: 'Components have different lengths; only whole-sample offsets are trimmed to the common overlap (reported).',
    time_misaligned: 'Component start times differ by a fraction of a sample. Sub-sample shifts are not applied automatically.',
    gaps: 'The trace contains gaps. Gaps are never interpolated; split or repair the data before importing.',
    overlaps: 'Overlapping segments were found in the MiniSEED data.',
    duplicate_timestamps: 'Duplicate time stamps in the time column.',
    irregular_sampling: 'The time column is not regularly sampled.',
    nan_values: 'Non-numeric or NaN samples were found. They are never interpolated.',
    constant_channel: 'A component is constant (dead channel).',
    clipping_suspected: 'Many samples sit at the extreme value — possible clipping; consider rejecting those windows.',
    no_timing_information: 'No sampling rate or time column: provide the sampling rate.',
    short_record: 'The record is short; few windows will be available.',
    unit_unknown: 'Units are unknown; HVSR is unit-independent but spectra are labelled in counts.',
    trimmed_to_overlap: 'Components were trimmed to their common time overlap (whole samples only).',
};
</script>

<template>
    <div class="p-6 max-w-6xl space-y-5">
        <PageHeader title="Import recordings" subtitle="Bring in TXT/ASCII, CSV, SAF (SESAME ASCII), MiniSEED, GSE2, SEG-2 or SAC files, map the N, E and Z components explicitly, and validate before analysis.">
            <template #below>
                <div class="segmented mt-4" role="tablist" aria-label="Import steps">
                    <button v-for="(s, i) in steps" :key="s" role="tab" class="seg-btn" :class="{ active: step === i + 1 }" :aria-selected="step === i + 1" :disabled="i + 1 > step" :title="i + 1 > step ? 'Complete the previous step first' : ''" @click="step = i + 1">
                        <span class="grid place-items-center size-4 rounded-full text-[10px] font-semibold" :class="step === i + 1 ? 'bg-brand-500 text-white' : step > i + 1 ? 'bg-ok-500/15 text-ok-500' : 'bg-black/8 text-muted dark:bg-white/12'"><Check v-if="step > i + 1" class="size-2.5" /><template v-else>{{ i + 1 }}</template></span>{{ s }}
                    </button>
                </div>
            </template>
        </PageHeader>

        <!-- Step 1 -->
        <template v-if="step === 1">
            <div
                class="rounded-lg border-2 border-dashed p-8 text-center transition"
                :class="dragOver ? 'border-brand-400 bg-brand-600/5' : 'border-ui-strong'"
                @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="onDrop"
            >
                <UploadCloud class="size-8 mx-auto text-faint" />
                <p class="mt-2 text-[13px] font-medium">Drop files here, or <button class="underline text-brand-600 dark:text-brand-300" @click="fileInput?.click()">browse</button></p>
                <p class="text-[12px] text-muted">Several files at once are fine — three separate component files, one multicolumn file, a SESAME .saf file, or MiniSEED / GSE2 / SEG-2 / SAC with multiple traces.</p>
                <input ref="fileInput" type="file" multiple class="hidden" accept=".txt,.csv,.dat,.asc,.tsv,.saf,.mseed,.msd,.miniseed,.seed,.gse,.gse2,.seg,.sg2,.seg2,.sac,*" @change="addFiles(($event.target as HTMLInputElement).files ?? [])" />
                <p v-if="uploading" class="mt-2 text-[12px] text-muted">Uploading and inspecting…</p>
            </div>
            <ErrorBanner v-if="uploadError" :error="uploadError" />
            <Panel v-if="uploads.length" title="Staged files" :padded="false">
                <table class="table hover">
                    <thead><tr><th>File</th><th>Size</th><th>Format</th><th>Detected</th><th>SHA-256</th><th></th></tr></thead>
                    <tbody>
                        <tr v-for="u in uploads" :key="u.upload_id">
                            <td class="font-medium"><FileText class="size-3.5 inline mr-1 text-faint" />{{ u.name }}</td>
                            <td class="num">{{ fmtBytes(u.size) }}</td>
                            <td><Badge :tone="u.inspect.format === 'unknown' ? 'bad' : 'brand'">{{ u.inspect.format }}</Badge></td>
                            <td class="text-[11.5px] text-muted">
                                <template v-if="u.inspect.ascii">{{ u.inspect.ascii.columns.length }} columns, delimiter {{ u.inspect.ascii.delimiter === '\t' ? 'tab' : u.inspect.ascii.delimiter }}, ~{{ u.inspect.ascii.n_rows_estimate }} rows<span v-if="u.inspect.ascii.time_column_guess?.kind">, time column ({{ u.inspect.ascii.time_column_guess.kind }}{{ u.inspect.ascii.time_column_guess.sample_rate_estimate ? `, ≈${fmtNum(u.inspect.ascii.time_column_guess.sample_rate_estimate, 5)} Hz` : '' }})</span></template>
                                <template v-else-if="u.inspect.saf">SESAME ASCII · {{ u.inspect.saf.channels?.join(', ') ?? '3 channels' }} · {{ u.inspect.saf.sample_rate ?? '?' }} Hz</template>
                                <template v-else-if="u.inspect.mseed">{{ u.inspect.mseed.traces.length }} trace(s): {{ u.inspect.mseed.traces.map((t) => t.channel).join(', ') }}</template>
                                <template v-else>{{ u.inspect.error ?? 'Unrecognised format' }}</template>
                            </td>
                            <td class="num text-[11px] text-faint">{{ (u.sha256 ?? u.inspect.sha256 ?? '').slice(0, 12) }}</td>
                            <td><button class="text-faint hover:text-bad-500 p-1" @click="removeUpload(u.upload_id)"><XCircle class="size-4" /></button></td>
                        </tr>
                    </tbody>
                </table>
            </Panel>
            <div class="flex justify-end">
                <Button variant="primary" :disabled="uploads.filter((u) => u.inspect.format !== 'unknown').length === 0" @click="step = asciiUploads.length ? 2 : 3; if (!asciiUploads.length) enterMapping()">Next <ArrowRight class="size-4" /></Button>
            </div>
        </template>

        <!-- Step 2 -->
        <template v-else-if="step === 2">
            <div class="grid grid-cols-[260px_1fr] gap-4">
                <Panel title="ASCII files" :padded="false">
                    <ul>
                        <li v-for="u in asciiUploads" :key="u.upload_id">
                            <button class="w-full text-left px-3 py-2 text-[12.5px] hover:bg-surface-2 truncate" :class="previewUpload?.upload_id === u.upload_id ? 'bg-surface-2 font-medium' : ''" @click="previewFile = u.upload_id">{{ u.name }}</button>
                        </li>
                    </ul>
                </Panel>
                <div v-if="previewUpload" class="space-y-3">
                    <Panel :title="`Parsing settings — ${previewUpload.name}`">
                        <div class="grid grid-cols-4 gap-3">
                            <Field label="Delimiter"><Select v-model="cfgFor(previewUpload).delimiter" :options="delimiterOptions" /></Field>
                            <Field label="Decimal mark"><Select v-model="cfgFor(previewUpload).decimal" :options="[{ value: '.', label: 'Point (.)' }, { value: ',', label: 'Comma (,)' }]" /></Field>
                            <Field label="Header rows"><NumberInput v-model="cfgFor(previewUpload).header_rows" :min="0" :max="200" :step="1" /></Field>
                            <Field label="Comment prefix"><input v-model="cfgFor(previewUpload).comment_prefix" class="input num" placeholder="#" /></Field>
                        </div>
                        <p class="help">Header rows are skipped after comment lines are removed. Check the parsed table below before mapping columns.</p>
                    </Panel>
                    <Panel title="Raw lines (first 40)" :padded="false">
                        <pre class="num text-[11px] leading-4 p-3 overflow-auto max-h-48 scroll-thin">{{ (previewUpload.inspect.ascii?.preview_lines ?? []).join('\n') }}</pre>
                    </Panel>
                    <Panel title="Parsed preview" :padded="false">
                        <div class="overflow-auto max-h-64 scroll-thin">
                            <table v-if="preview" class="table">
                                <thead><tr><th v-for="i in preview.nCols" :key="i">Column {{ i }}</th></tr></thead>
                                <tbody><tr v-for="(r, ri) in preview.rows" :key="ri"><td v-for="i in preview.nCols" :key="i" class="num">{{ r[i - 1] ?? '' }}</td></tr></tbody>
                            </table>
                        </div>
                    </Panel>
                </div>
            </div>
            <div class="flex justify-between">
                <Button @click="step = 1"><ArrowLeft class="size-4" />Back</Button>
                <Button variant="primary" @click="enterMapping">Next <ArrowRight class="size-4" /></Button>
            </div>
        </template>

        <!-- Step 3 -->
        <template v-else-if="step === 3">
            <div class="grid grid-cols-2 gap-4">
                <Panel title="Components">
                    <div class="flex gap-2 mb-3">
                        <button class="flex-1 rounded-md border px-3 py-2 text-left text-[12.5px]" :class="mode === 'single' ? 'border-brand-400 bg-brand-600/5' : 'border-ui'" @click="mode = 'single'; autoMap()"><div class="font-medium">One file with all components</div><div class="text-faint text-[11.5px]">Multicolumn ASCII, SAF, or seismic traces (MiniSEED, GSE2, SEG-2, SAC)</div></button>
                        <button class="flex-1 rounded-md border px-3 py-2 text-left text-[12.5px]" :class="mode === 'split' ? 'border-brand-400 bg-brand-600/5' : 'border-ui'" :disabled="asciiUploads.length < 3" @click="mode = 'split'; timeMode = 'sample_rate'"><div class="font-medium">Three separate files</div><div class="text-faint text-[11.5px]">One ASCII file per component</div></button>
                    </div>

                    <template v-if="mode === 'single'">
                        <Field label="File" help="For trace formats, traces from all staged files are listed."><Select v-model="singleFileId" :options="uploads.filter((u) => u.inspect.format !== 'unknown').map((u) => ({ value: u.upload_id, label: u.name }))" @update:model-value="autoMap" /></Field>
                        <p v-if="sourceKind === 'saf'" class="text-[12.5px] text-muted mt-2">SESAME ASCII format: the three channels (CH0/CH1/CH2 = V/N/E), the sampling rate and the start time come from the file header; nothing to map.</p>
                        <div v-if="isTraceKind" class="space-y-2 mt-2">
                            <Field v-for="c in (['n', 'e', 'z'] as ComponentKey[])" :key="c" :label="`${c.toUpperCase()} component ${c === 'z' ? '(vertical)' : '(horizontal)'}`"><Select v-model="traces[c]" :options="traceOptions" placeholder="Select trace" /></Field>
                            <p v-if="allTraces.some((t) => t.trace.has_gaps)" class="text-[11.5px] text-warn-500">Some traces contain gaps; the import will be rejected for those. Gaps are never interpolated.</p>
                        </div>
                        <div v-else class="space-y-2 mt-2">
                            <Field v-for="c in (['n', 'e', 'z'] as ComponentKey[])" :key="c" :label="`${c.toUpperCase()} component ${c === 'z' ? '(vertical)' : '(horizontal)'}`"><Select v-model="columns[c]" :options="colOptions(singleFile)" placeholder="Select column" /></Field>
                        </div>
                    </template>
                    <template v-else>
                        <div v-for="c in (['n', 'e', 'z'] as ComponentKey[])" :key="c" class="grid grid-cols-[1fr_160px] gap-2 mb-2">
                            <Field :label="`${c.toUpperCase()} file`"><Select v-model="splitFiles[c]" :options="asciiUploads.map((u) => ({ value: u.upload_id, label: u.name }))" placeholder="Select file" /></Field>
                            <Field label="Column"><Select v-model="splitColumns[c]" :options="colOptions(uploads.find((u) => u.upload_id === splitFiles[c]) ?? null)" /></Field>
                        </div>
                    </template>
                </Panel>

                <div class="space-y-4">
                    <Panel v-if="sourceKind === 'ascii'" title="Timing">
                        <Field label="Time information">
                            <Select v-model="timeMode" :options="[{ value: 'sample_rate', label: 'Constant sampling rate (no time column)' }, { value: 'seconds_column', label: 'Time column in seconds', disabled: mode === 'split' }, { value: 'datetime_column', label: 'Time column with date/time', disabled: mode === 'split' }]" />
                        </Field>
                        <div class="grid grid-cols-2 gap-3 mt-2">
                            <Field v-if="timeMode === 'sample_rate'" label="Sampling rate" :error="!sampleRate ? 'Required — the file carries no timing.' : null"><NumberInput v-model="sampleRate" :min="0.0001" unit="Hz" /></Field>
                            <Field v-else label="Time column"><Select v-model="timeColumn" :options="colOptions(singleFile)" placeholder="Select column" /></Field>
                            <Field v-if="timeMode === 'datetime_column'" label="Datetime format" help="Optional strptime pattern; auto-detected when empty."><input v-model="datetimeFormat" class="input num" placeholder="%Y-%m-%d %H:%M:%S.%f" /></Field>
                            <Field v-if="timeMode !== 'datetime_column'" label="Start time (UTC)" help="Optional; defaults to 1970-01-01 when unknown."><input v-model="startTime" type="datetime-local" step="1" class="input num" /></Field>
                        </div>
                        <p v-if="timeMode !== 'sample_rate'" class="help">The sampling rate is derived from the time column and checked for regularity and duplicates.</p>
                    </Panel>
                    <Panel v-else title="Timing">
                        <p class="text-[12.5px] text-muted">Start time and sampling rate are taken from the file headers of the selected traces and cross-checked between components.</p>
                    </Panel>

                    <Panel title="Units & metadata">
                        <div class="grid grid-cols-3 gap-3">
                            <Field label="Units"><input v-model="units" class="input" placeholder="counts" /></Field>
                            <Field label="Unit kind"><Select v-model="unitKind" :options="[{ value: 'raw', label: 'Raw counts' }, { value: 'velocity', label: 'Velocity' }, { value: 'acceleration', label: 'Acceleration' }, { value: 'displacement', label: 'Displacement' }, { value: 'unknown', label: 'Unknown' }]" /></Field>
                            <Field label="Scale factor" help="Multiplied into every sample."><NumberInput v-model="scaleFactor" /></Field>
                        </div>
                        <div class="grid grid-cols-2 gap-3 mt-2">
                            <Field label="Recording name"><input v-model="recName" class="input" /></Field>
                            <Field label="Station"><Select v-model="stationId" :options="stationOptions" /></Field>
                            <Field v-if="!stationId" label="New station code" help='Use "-" to leave unassigned.'><input v-model="newStationCode" class="input" placeholder="STA1" /></Field>
                            <Field label="Sensor N azimuth" help="Degrees clockwise from true north; 0 = aligned."><NumberInput v-model="orientation" unit="°" /></Field>
                        </div>
                        <Toggle v-model="isSynthetic" label="This is synthetic (not field) data" class="mt-2" />
                    </Panel>
                </div>
            </div>
            <ul v-if="mappingErrors.length" class="rounded-md border border-warn-500/40 bg-warn-500/8 p-3 space-y-1 text-[12.5px]">
                <li v-for="e in mappingErrors" :key="e" class="flex gap-2"><AlertTriangle class="size-4 text-warn-500 shrink-0" />{{ e }}</li>
            </ul>
            <div class="flex justify-between">
                <Button @click="step = asciiUploads.length ? 2 : 1"><ArrowLeft class="size-4" />Back</Button>
                <Button variant="primary" :disabled="mappingErrors.length > 0" @click="step = 4">Next <ArrowRight class="size-4" /></Button>
            </div>
        </template>

        <!-- Step 4 -->
        <template v-else>
            <Panel title="Validate & create recording">
                <dl class="grid grid-cols-[180px_1fr] gap-y-1 text-[12.5px]">
                    <dt class="text-muted">Recording</dt><dd class="font-medium">{{ recName }}</dd>
                    <dt class="text-muted">Station</dt><dd>{{ store.station(stationId)?.code ?? (newStationCode === '-' ? 'unassigned' : newStationCode) }}</dd>
                    <dt class="text-muted">Format</dt><dd class="uppercase">{{ sourceKind }} · {{ mode === 'single' ? 'single file' : 'three files' }}</dd>
                    <dt class="text-muted">Components</dt>
                    <dd class="num text-[12px]">
                        <template v-if="isTraceKind">N={{ traces.n }} · E={{ traces.e }} · Z={{ traces.z }}</template><template v-else-if="sourceKind === 'saf'">from the SAF header</template>
                        <template v-else-if="mode === 'single'">N=col {{ (columns.n ?? 0) + 1 }} · E=col {{ (columns.e ?? 0) + 1 }} · Z=col {{ (columns.z ?? 0) + 1 }}</template>
                        <template v-else>N={{ uploads.find((u) => u.upload_id === splitFiles.n)?.name }} · E={{ uploads.find((u) => u.upload_id === splitFiles.e)?.name }} · Z={{ uploads.find((u) => u.upload_id === splitFiles.z)?.name }}</template>
                    </dd>
                    <dt class="text-muted">Timing</dt><dd>{{ isTraceKind || sourceKind === 'saf' ? 'from file headers' : timeMode === 'sample_rate' ? `${sampleRate} Hz` : `${timeMode.replace('_', ' ')} (column ${(timeColumn ?? 0) + 1})` }}</dd>
                    <dt class="text-muted">Units</dt><dd>{{ units }} ({{ unitKind }}), ×{{ scaleFactor }}</dd>
                </dl>
                <p class="help mt-3">The engine checks component overlap, sampling rates, lengths, time alignment, gaps, duplicate time stamps, NaNs, clipping and constant channels. Nothing is interpolated, resampled, rotated or substituted.</p>
            </Panel>

            <ErrorBanner v-if="createError" :error="createError" />

            <Panel v-if="validation" :title="validation.blocking ? 'Import blocked by validation errors' : 'Validation results'">
                <div v-for="sev in (['error', 'warning', 'info'] as const)" :key="sev">
                    <ul v-if="issuesBySeverity[sev].length" class="space-y-2 mb-3">
                        <li v-for="(i, k) in issuesBySeverity[sev]" :key="k" class="flex gap-2 text-[12.5px]">
                            <component :is="sev === 'error' ? XCircle : sev === 'warning' ? AlertTriangle : Info" class="size-4 shrink-0 mt-0.5" :class="sev === 'error' ? 'text-bad-500' : sev === 'warning' ? 'text-warn-500' : 'text-brand-400'" />
                            <div>
                                <div class="font-medium">{{ i.message }} <span class="num text-faint text-[11px]">{{ i.code }}</span></div>
                                <div v-if="ISSUE_HELP[i.code]" class="text-muted">{{ ISSUE_HELP[i.code] }}</div>
                                <pre v-if="i.details && Object.keys(i.details).length" class="num text-[11px] text-faint mt-0.5 whitespace-pre-wrap">{{ JSON.stringify(i.details) }}</pre>
                            </div>
                        </li>
                    </ul>
                </div>
                <p v-if="!validation.issues.length" class="flex items-center gap-2 text-ok-500 text-[12.5px]"><CheckCircle2 class="size-4" />No issues found.</p>
            </Panel>

            <div class="flex justify-between">
                <Button @click="step = 3"><ArrowLeft class="size-4" />Back to mapping</Button>
                <Button variant="primary" :loading="creating" @click="create">{{ validation?.blocking ? 'Retry import' : 'Validate & create recording' }}</Button>
            </div>
        </template>
    </div>
</template>
