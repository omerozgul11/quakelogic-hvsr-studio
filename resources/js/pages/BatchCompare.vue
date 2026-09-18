<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue';
import { useRoute, RouterLink } from 'vue-router';
import { Layers, Play, XCircle, Upload } from 'lucide-vue-next';
import { api } from '@/api';
import type { Batch, CompareEntry, Recording } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Field from '@/components/ui/Field.vue';
import Select from '@/components/ui/Select.vue';
import StatusDot from '@/components/ui/StatusDot.vue';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import PageHeader from '@/components/PageHeader.vue';
import ComparePlot from '@/components/plots/ComparePlot.vue';
import { fmtNum, fmtHz, fmtDate } from '@/utils/format';

const route = useRoute();
const store = useProjectStore();
const toast = useToastStore();
const pid = computed(() => String(route.params.p));
const error = ref<unknown>(null);

// ---- comparison ----
const selected = ref<Set<string>>(new Set());
const entries = shallowRef<CompareEntry[]>([]);
const comparing = ref(false);
const showBands = ref(false);
function toggleSel(id: string) { const s = new Set(selected.value); if (s.has(id)) s.delete(id); else s.add(id); selected.value = s; }
function toggleAll(rec: Recording) {
    const ids = (rec.analyses ?? []).filter((a) => a.status === 'done').map((a) => a.id);
    const s = new Set(selected.value);
    const all = ids.every((i) => s.has(i));
    ids.forEach((i) => (all ? s.delete(i) : s.add(i)));
    selected.value = s;
}
const external = ref<CompareEntry[]>([]);
const curveInput = ref<HTMLInputElement | null>(null);
async function compare() {
    comparing.value = true;
    try { const res = selected.value.size ? await api.projects.compare(pid.value, [...selected.value]) : []; entries.value = [...res, ...external.value]; }
    catch (e) { toast.error('Comparison failed', (e as Error).message); } finally { comparing.value = false; }
}
async function loadCurve(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    (ev.target as HTMLInputElement).value = '';
    if (!f) return;
    try {
        const c = await api.projects.importCurve(pid.value, f);
        const name = c.name || f.name;
        external.value = [...external.value, { analysis_id: `external-${Date.now()}`, name: `Loaded: ${name}`, recording_id: '', recording_name: c.format === 'geopsy_hv' ? 'Geopsy .hv file' : 'external curve', station_code: null, frequency: c.frequency, curve: c.values, lower: c.lower ?? c.values, upper: c.upper ?? c.values, peak: null, peak_status: null, band: c.lower ? 'min/max from file' : undefined }];
        entries.value = [...entries.value.filter((e) => !e.analysis_id.startsWith('external-')), ...external.value];
        toast.success('Curve loaded', name);
    } catch (e) { toast.error('Could not load the curve', (e as Error).message); }
}
function clearExternal() { external.value = []; entries.value = entries.value.filter((e) => !e.analysis_id.startsWith('external-')); }
const recordingsWithAnalyses = computed(() => store.recordings.filter((r) => (r.analyses ?? []).some((a) => a.status === 'done')));

// ---- batch runner ----
const presetId = ref<string | null>(null);
const runSteps = ref(true);
const batchName = ref('');
const recSel = ref<Set<string>>(new Set());
const starting = ref(false);
const batches = ref<Batch[]>([]);
const presetOptions = computed(() => store.presets.map((p) => ({ value: p.id, label: p.name })));
const preset = computed(() => store.presets.find((p) => p.id === presetId.value) ?? null);
function toggleRec(id: string) { const s = new Set(recSel.value); if (s.has(id)) s.delete(id); else s.add(id); recSel.value = s; }
async function startBatch() {
    starting.value = true;
    try {
        const b = await api.projects.createBatch(pid.value, { name: batchName.value.trim() || `Batch ${fmtDate(new Date().toISOString())}`, preset_id: presetId.value, recording_ids: [...recSel.value], run_steps: runSteps.value && (preset.value?.steps?.length ?? 0) > 0 });
        batches.value.unshift(b);
        toast.info('Batch started', `${b.items.length} recording(s)`);
        recSel.value = new Set();
    } catch (e) { toast.error('Could not start batch', (e as Error).message); } finally { starting.value = false; }
}
async function cancelBatch(id: string) {
    try { const b = await api.batches.cancel(id); replace(b); } catch (e) { toast.error('Could not cancel', (e as Error).message); }
}
function replace(b: Batch) { const i = batches.value.findIndex((x) => x.id === b.id); if (i >= 0) batches.value[i] = b; else batches.value.unshift(b); }
let timer: number | null = null;
async function pollBatches() {
    const active = batches.value.filter((b) => b.status === 'queued' || b.status === 'running');
    if (!active.length) return;
    for (const b of active) {
        try { const nb = await api.batches.get(b.id); replace(nb); if (nb.status !== 'queued' && nb.status !== 'running') { await store.refresh(); toast.success('Batch finished', nb.name); } } catch { /* transient */ }
    }
}
function batchProgress(b: Batch): number {
    const n = b.items.length || 1;
    const done = b.items.filter((i) => ['done', 'failed', 'skipped', 'cancelled'].includes(i.status)).length;
    const running = b.items.find((i) => i.status === 'running');
    return (done + (running?.progress ?? 0)) / n;
}
onMounted(async () => {
    try {
        const p = await store.open(pid.value, true);
        batches.value = [...(p.batches ?? [])].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
        timer = window.setInterval(() => void pollBatches(), 1500);
    } catch (e) { error.value = e; }
});
onBeforeUnmount(() => { if (timer) window.clearInterval(timer); });
</script>

<template>
    <div class="p-6 space-y-5">
        <ErrorBanner v-if="error" :error="error" />
        <PageHeader title="Batch & compare" subtitle="Apply a saved preset to many recordings, then overlay the resulting H/V curves across stations or processing runs." />

        <div class="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-4">
            <Panel title="Batch runner">
                <Field label="Preset" help="Processing steps (optional) and HVSR parameters."><Select v-model="presetId" :options="presetOptions" placeholder="Select preset" /></Field>
                <Toggle v-model="runSteps" label="Apply the preset's processing steps first" small class="mt-2" :disabled="!(preset?.steps?.length)" />
                <Field label="Batch name" class="mt-2"><input v-model="batchName" class="input" placeholder="optional" /></Field>
                <div class="mt-3 text-[12px] font-medium text-muted">Recordings</div>
                <ul class="max-h-56 overflow-auto scroll-thin mt-1 space-y-0.5">
                    <li v-for="r in store.recordings.filter((x) => x.status === 'ready')" :key="r.id">
                        <label class="flex items-center gap-2 text-[12.5px] px-1 py-0.5 rounded hover:bg-surface-2 cursor-pointer">
                            <input type="checkbox" :checked="recSel.has(r.id)" @change="toggleRec(r.id)" />
                            <span class="truncate">{{ r.name }}</span><span class="text-faint num text-[11px] ml-auto">{{ store.station(r.station_id)?.code ?? '' }}</span>
                        </label>
                    </li>
                    <li v-if="!store.recordings.length" class="text-faint text-[12px] px-1">No recordings in this project.</li>
                </ul>
                <div class="flex items-center justify-between mt-3">
                    <button class="text-[11.5px] underline text-muted" @click="recSel = new Set(recSel.size === store.recordings.length ? [] : store.recordings.filter((x) => x.status === 'ready').map((x) => x.id))">{{ recSel.size ? 'Clear' : 'Select all' }}</button>
                    <Button variant="primary" :loading="starting" :disabled="!presetId || recSel.size === 0" @click="startBatch"><Play class="size-4" />Run batch ({{ recSel.size }})</Button>
                </div>
            </Panel>

            <Panel title="Batch queue" :padded="false">
                <EmptyState v-if="!batches.length" title="No batches yet" description="Choose a preset and recordings, then run. Each recording is processed independently; a failure does not stop the others." :icon="Layers" />
                <div v-for="b in batches" :key="b.id" class="border-b border-ui last:border-0 p-3 space-y-2">
                    <div class="flex items-center gap-2 text-[12.5px]">
                        <StatusDot :status="b.status" />
                        <span class="font-medium">{{ b.name }}</span>
                        <Badge>{{ b.preset?.name ?? 'preset' }}</Badge>
                        <span class="text-faint num text-[11px]">{{ fmtDate(b.created_at) }}</span>
                        <div class="flex-1" />
                        <span class="num text-[11.5px] text-muted">{{ b.items.filter((i) => i.status === 'done').length }}/{{ b.items.length }} done</span>
                        <Button v-if="b.status === 'queued' || b.status === 'running'" size="sm" variant="ghost" @click="cancelBatch(b.id)"><XCircle class="size-3.5" />Cancel</Button>
                    </div>
                    <ProgressBar :value="batchProgress(b)" :tone="b.status === 'cancelled' ? 'bad' : 'brand'" />
                    <table class="table">
                        <thead><tr><th>#</th><th>Recording</th><th>Status</th><th>Analysis</th><th>Error</th></tr></thead>
                        <tbody>
                            <tr v-for="it in b.items" :key="it.id">
                                <td class="num">{{ it.position + 1 }}</td>
                                <td>{{ it.recording?.name ?? store.recording(it.recording_id)?.name ?? it.recording_id }}</td>
                                <td><Badge :tone="it.status === 'done' ? 'ok' : it.status === 'failed' ? 'bad' : it.status === 'running' ? 'brand' : 'neutral'">{{ it.status }}</Badge><span v-if="it.status === 'running' && it.progress" class="num text-[11px] text-faint ml-1">{{ Math.round((it.progress ?? 0) * 100) }}%</span></td>
                                <td><RouterLink v-if="it.analysis_id" :to="`/analyses/${it.analysis_id}`" class="underline">open</RouterLink></td>
                                <td class="text-bad-500 text-[11.5px]">{{ it.error ?? '' }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </Panel>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-4">
            <Panel title="Select analyses to compare" :padded="false">
                <p v-if="!recordingsWithAnalyses.length" class="p-3 text-faint text-[12.5px]">No completed analyses yet.</p>
                <ul class="p-2 space-y-2 max-h-[420px] overflow-auto scroll-thin">
                    <li v-for="r in recordingsWithAnalyses" :key="r.id">
                        <label class="flex items-center gap-2 text-[12.5px] font-medium cursor-pointer">
                            <input type="checkbox" :checked="(r.analyses ?? []).filter((a) => a.status === 'done').every((a) => selected.has(a.id))" @change="toggleAll(r)" />
                            {{ r.name }} <span class="text-faint font-normal">{{ store.station(r.station_id)?.code ?? '' }}</span>
                        </label>
                        <ul class="ml-5 mt-1 space-y-0.5">
                            <li v-for="a in (r.analyses ?? []).filter((a) => a.status === 'done')" :key="a.id">
                                <label class="flex items-center gap-2 text-[12px] cursor-pointer"><input type="checkbox" :checked="selected.has(a.id)" @change="toggleSel(a.id)" /><span class="truncate">{{ a.name }}</span><span class="num text-faint ml-auto shrink-0 whitespace-nowrap text-[11px]">{{ fmtHz(a.summary?.f0) }}</span></label>
                            </li>
                        </ul>
                    </li>
                </ul>
                <div class="flex flex-wrap items-center gap-2 p-3 border-t border-ui">
                    <Toggle v-model="showBands" label="Show bands" small />
                    <input ref="curveInput" type="file" accept=".hv,.csv,.txt" class="hidden" @change="loadCurve" />
                    <Button size="sm" title="Overlay an H/V curve from a Geopsy .hv or CSV file" @click="curveInput?.click()"><Upload class="size-3.5" />Load curve from file</Button>
                    <button v-if="external.length" class="text-[11.5px] underline text-faint" @click="clearExternal">clear {{ external.length }} loaded</button>
                    <div class="flex-1" />
                    <Button variant="primary" :loading="comparing" :disabled="selected.size === 0 && external.length === 0" @click="compare">Compare ({{ selected.size + external.length }})</Button>
                </div>
            </Panel>
            <Panel :padded="false">
                <EmptyState v-if="!entries.length" title="No comparison yet" description="Select two or more analyses and press Compare to overlay their mean H/V curves." />
                <template v-else>
                    <div class="p-2"><ComparePlot :entries="entries" :show-bands="showBands" /></div>
                    <table class="table hover">
                        <thead><tr><th>Analysis</th><th>Recording</th><th>Statistic</th><th>f0</th><th>A0</th><th>Peak status</th><th>Windows</th></tr></thead>
                        <tbody>
                            <tr v-for="e in entries" :key="e.analysis_id">
                                <td><RouterLink :to="`/analyses/${e.analysis_id}`" class="font-medium hover:underline">{{ e.name }}</RouterLink></td>
                                <td>{{ e.recording_name ?? store.recording(e.recording_id)?.name ?? '' }}<span v-if="e.station_code" class="text-faint"> · {{ e.station_code }}</span></td>
                                <td class="text-[11.5px] text-muted">{{ e.band ?? '' }}</td>
                                <td class="num">{{ e.peak ? fmtHz(e.peak.frequency) : '—' }}</td>
                                <td class="num">{{ e.peak ? fmtNum(e.peak.amplitude, 3) : '—' }}</td>
                                <td><Badge :tone="e.peak_status === 'clear' ? 'ok' : 'neutral'">{{ e.peak_status ?? '—' }}</Badge></td>
                                <td class="num">{{ e.windows?.accepted ?? '—' }}/{{ e.windows?.total ?? '—' }}</td>
                            </tr>
                        </tbody>
                    </table>
                </template>
            </Panel>
        </div>
    </div>
</template>
