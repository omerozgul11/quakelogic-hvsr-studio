<script setup lang="ts">
import { computed, markRaw, onMounted, reactive, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowRight, Trash2, X } from 'lucide-vue-next';
import PageHeader from '@/components/PageHeader.vue';
import { api } from '@/api';
import type { DisplayData, Recording, WindowItem, WindowOverrides, WindowsResult, WindowSetExport } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import { useUnits } from '@/composables/useUnits';
import { useProcessingPanel, type PanelContent } from '@/composables/usePanel';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import WindowsPlot from '@/components/plots/WindowsPlot.vue';
import SeismogramPlayer from '@/components/SeismogramPlayer.vue';
import WindowsPanel, { type WindowsController } from './hvsr/WindowsPanel.vue';
import { defaultHvsrParams, syncWindowAliases, validateHvsrParams } from '@/components/processing/defaults';
import { loadDraft, saveDraft } from './hvsr/draft';
import { windowColorFor } from '@/utils/windowPalette';
import { fmtNum } from '@/utils/format';

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const toast = useToastStore();
const rid = computed(() => String(route.params.r));
const recording = ref<Recording | null>(null);
const error = ref<unknown>(null);
const data = shallowRef<DisplayData | null>(null);
const unitsUi = useUnits();
const result = ref<WindowsResult | null>(null);
const overrides = reactive<WindowOverrides>({});
/** Automatic decision per window index (before overrides), so Invert/Clear can restore it. */
const auto = reactive<Record<string, boolean>>({});
const loading = ref(false);
const range = ref<[number, number] | null>(null);
const cursor = ref<number | null>(null);
const bookmarks = ref<number[]>(loadBookmarks());

function bookmarkKey() { return `hvsr-bookmarks:${rid.value}`; }
function loadBookmarks(): number[] { try { return JSON.parse(localStorage.getItem(`hvsr-bookmarks:${String(route.params.r)}`) ?? '[]') as number[]; } catch { return []; } }
watch(bookmarks, (b) => { try { localStorage.setItem(bookmarkKey(), JSON.stringify(b)); } catch { /* ignore */ } }, { deep: true });

const draft = loadDraft(rid.value);
const ctl = reactive<WindowsController>({
    params: draft?.params ?? defaultHvsrParams(),
    fs: null,
    duration: null,
    runId: draft?.runId ?? (typeof route.query.run === 'string' ? route.query.run : null),
    runOptions: [],
    computing: false,
    errors: [],
    overridesCount: 0,
    freeSelect: false,
    hideSelected: false,
    commonY: false,
    async compute() {
        if (!recording.value) return;
        ctl.computing = true;
        try {
            syncWindowAliases(ctl.params);
            result.value = await api.recordings.windows(rid.value, { run_id: ctl.runId, params: JSON.parse(JSON.stringify(ctl.params)), window_overrides: JSON.parse(JSON.stringify(overrides)) });
            for (const w of result.value.windows) if (!overrides[String(w.index)]) auto[String(w.index)] = w.accepted;
            persist();
        } catch (e) { toast.error('Window screening failed', (e as Error).message); } finally { ctl.computing = false; }
    },
    resetOverrides() { for (const k of Object.keys(overrides)) delete overrides[k]; ctl.overridesCount = 0; void ctl.compute(); },
    setRun(id) { ctl.runId = id; result.value = null; void loadData(); },
    saveWindows() {
        if (!result.value) { toast.warning('Compute windows first'); return; }
        const set: WindowSetExport = { mode: ctl.params.windows.mode, params: ctl.params.windows, windows: result.value.windows.map((w) => ({ start_s: w.start_s, end_s: w.end_s, accepted: w.accepted, reason: w.reason })) };
        const blob = new Blob([JSON.stringify(set, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${recording.value?.name ?? 'windows'}-windows.json`;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    },
    async loadWindows(file: File) {
        try {
            const body = JSON.parse(await file.text()) as WindowSetExport;
            if (!Array.isArray(body.windows)) throw new Error('Not a window set (missing "windows").');
            let custom: [number, number][];
            let ov: WindowOverrides = {};
            try {
                const res = await api.recordings.importWindows(rid.value, body);
                custom = res.custom;
                ov = res.window_overrides ?? {};
            } catch {
                custom = body.windows.map((w) => [Number(w.start_s), Number(w.end_s)] as [number, number]);
                body.windows.forEach((w, i) => { if (w.accepted === false) ov[String(i)] = { accepted: false, reason: 'manual' }; });
            }
            ctl.params.windows.mode = 'custom';
            ctl.params.windows.custom = custom.sort((x, y) => x[0] - y[0]);
            for (const k of Object.keys(overrides)) delete overrides[k];
            Object.assign(overrides, ov);
            ctl.overridesCount = Object.keys(overrides).length;
            toast.success('Window set loaded', `${custom.length} windows`);
            await ctl.compute();
        } catch (e) { toast.error('Could not load window set', (e as Error).message); }
    },
});
if (draft) Object.assign(overrides, draft.overrides);
ctl.overridesCount = Object.keys(overrides).length;

const currentRun = computed(() => recording.value?.runs?.find((r) => r.id === ctl.runId) ?? null);
const fs = computed(() => currentRun.value?.meta?.fs ?? recording.value?.sample_rate ?? null);
watch([recording, currentRun], () => {
    ctl.fs = fs.value;
    ctl.duration = recording.value?.duration_s ?? null;
    ctl.runOptions = [{ value: null, label: 'Raw recording' }, ...(recording.value?.runs ?? []).map((r) => ({ value: r.id, label: r.name, disabled: r.status !== 'done' }))];
});
watch(() => JSON.stringify(ctl.params), () => { ctl.errors = validateHvsrParams(ctl.params, fs.value, recording.value?.duration_s); persist(); });

function persist() { saveDraft(rid.value, { params: ctl.params, overrides, runId: ctl.runId }); }

async function loadData() {
    loading.value = true;
    try { data.value = await api.recordings.data(rid.value, { run: ctl.runId, t_start: range.value?.[0] ?? null, t_end: range.value?.[1] ?? null, max_points: 4000 }); }
    catch (e) { error.value = e; } finally { loading.value = false; }
}
function setAccepted(w: WindowItem, accepted: boolean) {
    const key = String(w.index);
    const autoValue = auto[key] ?? w.accepted;
    if (accepted === autoValue) delete overrides[key];
    else overrides[key] = { accepted, reason: 'manual' };
    w.accepted = accepted;
}
function finish() { ctl.overridesCount = Object.keys(overrides).length; persist(); void ctl.compute(); }
function toggle(index: number) {
    const w = result.value?.windows.find((x) => x.index === index);
    if (!w) return;
    setAccepted(w, !w.accepted);
    finish();
}
function selectAll() { result.value?.windows.forEach((w) => setAccepted(w, true)); finish(); }
function invert() { result.value?.windows.forEach((w) => setAccepted(w, !w.accepted)); finish(); }
function clearAll() { result.value?.windows.forEach((w) => setAccepted(w, false)); finish(); }
function isCustom() { return ctl.params.windows.mode === 'custom'; }
function customFor(w: WindowItem): [number, number] | undefined {
    return ctl.params.windows.custom.find((c) => Math.abs(c[0] - w.start_s) < 1e-6 && Math.abs(c[1] - w.end_s) < 1e-6);
}
function updateWindow(w: WindowItem, field: 'start_s' | 'end_s', value: number) {
    const c = customFor(w);
    if (!c) return;
    if (field === 'start_s') c[0] = value; else c[1] = value;
    if (c[1] <= c[0]) { toast.warning('End must be after start'); return; }
    ctl.params.windows.custom.sort((x, y) => x[0] - y[0]);
    void ctl.compute();
}
function deleteWindow(w: WindowItem) {
    const c = customFor(w);
    if (!c) return;
    ctl.params.windows.custom = ctl.params.windows.custom.filter((x) => x !== c);
    delete overrides[String(w.index)];
    void ctl.compute();
}
function deleteAllCustom() { ctl.params.windows.custom = []; for (const k of Object.keys(overrides)) delete overrides[k]; ctl.overridesCount = 0; result.value = null; }
function drawWindow(r: [number, number]) {
    const p = ctl.params.windows;
    if (p.mode !== 'custom') {
        // Convert the current windows into a custom set so the drawn one is added, not replacing them.
        p.custom = (result.value?.windows ?? []).map((w) => [w.start_s, w.end_s] as [number, number]);
        p.mode = 'custom';
        toast.info('Switched to custom windows', 'The current windows were kept; the drawn window was added.');
    }
    p.custom.push([Number(r[0].toFixed(3)), Number(r[1].toFixed(3))]);
    p.custom.sort((x, y) => x[0] - y[0]);
    void ctl.compute();
}
function addBookmark(t: number) { bookmarks.value = [...bookmarks.value, Number(t.toFixed(2))].sort((a, b) => a - b); toast.info(`Bookmark at ${fmtNum(t, 4)} s`); }
function removeBookmark(i: number) { bookmarks.value = bookmarks.value.filter((_, k) => k !== i); }
function rejectBookmarked() {
    if (!result.value) return;
    let n = 0;
    for (const w of result.value.windows) {
        if (w.accepted && bookmarks.value.some((b) => b >= w.start_s && b <= w.end_s)) { setAccepted(w, false); n += 1; }
    }
    finish();
    toast.success(`${n} window${n === 1 ? '' : 's'} rejected`, 'Windows containing a bookmark.');
}
const t10 = computed(() => {
    const w = ctl.params.windows;
    const L = w.mode === 'fixed' ? w.length_s : w.mode === 'auto_variable' ? w.max_length_s : Math.max(0, ...(result.value?.windows.map((x) => x.end_s - x.start_s) ?? [0]));
    return L > 0 ? 10 / L : null;
});
const panelContent = computed<PanelContent | null>(() => ({ title: 'Window selection', component: markRaw(WindowsPanel), props: { ctl } }));
useProcessingPanel(panelContent);

function reasonLabel(w: WindowItem): string {
    if (w.accepted) return overrides[String(w.index)] ? 'manual accept' : 'accepted';
    return w.reason ?? 'rejected';
}
function goHvsr() {
    persist();
    void router.push(`/recordings/${rid.value}/hvsr${ctl.runId ? `?run=${ctl.runId}` : ''}`);
}
onMounted(async () => {
    try {
        recording.value = await store.ensureForRecording(rid.value);
        recording.value = store.recording(rid.value) ?? recording.value;
        ctl.errors = validateHvsrParams(ctl.params, fs.value, recording.value?.duration_s);
        await loadData();
        if (!ctl.errors.length) await ctl.compute();
    } catch (e) { error.value = e; }
});
</script>

<template>
    <div class="p-6 space-y-5">
        <ErrorBanner v-if="error" :error="error" />
        <template v-if="recording">
            <PageHeader :title="recording.name" steps>
                <template #subtitle>Window selection · {{ ctl.params.windows.mode === 'fixed' ? `${ctl.params.windows.length_s} s windows, ${Math.round(ctl.params.windows.overlap * 100)} % overlap` : ctl.params.windows.mode === 'auto_variable' ? `automatic ${ctl.params.windows.min_length_s}–${ctl.params.windows.max_length_s} s windows` : 'custom windows' }}<template v-if="t10"> · T10 = {{ fmtNum(t10, 3) }} Hz</template><template v-if="result"> · <span class="text-ok-500">{{ result.counts.accepted }} accepted</span>, <span class="text-bad-500">{{ result.counts.rejected }} rejected</span> of {{ result.counts.total }}</template></template>
                <template #actions>
                    <Button variant="primary" :disabled="!result" title="Continue with the HVSR analysis" @click="goHvsr">Next: HVSR <ArrowRight class="size-4" /></Button>
                </template>
            </PageHeader>

            <Panel :padded="false">
                <div class="p-2">
                    <WindowsPlot :data="unitsUi.convertDisplay(data, currentRun?.meta?.unit_kind ?? recording.unit_kind, currentRun?.meta?.units ?? recording.units)" :windows="result?.windows ?? []" :units="unitsUi.amplitudeLabel(currentRun?.meta?.unit_kind ?? recording.unit_kind, currentRun?.meta?.units ?? recording.units)" :channels="recording.meta?.channels" :loading="loading || ctl.computing" :hide-selected="ctl.hideSelected" :free-select="ctl.freeSelect" :common-y="ctl.commonY" :bookmarks="bookmarks" :cursor="cursor" @toggle="toggle" @draw="drawWindow" @range="(r) => { range = r; loadData(); }" />
                </div>
            </Panel>

            <div class="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4 items-start">
                <Panel title="Windows" :padded="false">
                    <template #actions>
                        <Button size="xs" :disabled="!result" @click="selectAll">Select all</Button>
                        <Button size="xs" :disabled="!result" @click="invert">Invert</Button>
                        <Button size="xs" :disabled="!result" @click="clearAll">Clear</Button>
                        <Button v-if="isCustom()" size="xs" variant="ghost" :disabled="!ctl.params.windows.custom.length" title="Remove every custom window" @click="deleteAllCustom"><Trash2 class="size-3.5" />Delete all</Button>
                    </template>
                    <EmptyState v-if="!result" title="No windows computed yet" :description="isCustom() ? 'Draw windows with Free selection, load a window set, or switch to Fixed / Automatic mode.' : 'Set the window length and screening criteria in the panel, then press Compute windows.'" />
                    <div v-else class="overflow-auto max-h-[460px] scroll-thin">
                        <table class="table hover">
                            <thead><tr><th></th><th>#</th><th>Start (s)</th><th>End (s)</th><th>Length (s)</th><th>Use</th><th>Reason</th><th>STA/LTA max</th><th>STA/LTA min</th><th>|x|max / RMS</th><th v-if="isCustom()"></th></tr></thead>
                            <tbody>
                                <tr v-for="w in result.windows" :key="w.index" :class="w.accepted ? '' : 'text-muted'">
                                    <td><span class="inline-block size-3.5 rounded-sm border border-black/10" :style="{ background: w.accepted ? windowColorFor(w, result.windows.length) : '#9aa0ab' }" /></td>
                                    <td class="num">{{ w.index }}</td>
                                    <td class="num"><input v-if="isCustom()" type="number" step="0.01" class="input !h-7 !py-0 w-24 num" :value="w.start_s" @change="updateWindow(w, 'start_s', Number(($event.target as HTMLInputElement).value))" /><template v-else>{{ fmtNum(w.start_s, 5) }}</template></td>
                                    <td class="num"><input v-if="isCustom()" type="number" step="0.01" class="input !h-7 !py-0 w-24 num" :value="w.end_s" @change="updateWindow(w, 'end_s', Number(($event.target as HTMLInputElement).value))" /><template v-else>{{ fmtNum(w.end_s, 5) }}</template></td>
                                    <td class="num">{{ fmtNum(w.length_s ?? w.end_s - w.start_s, 4) }}</td>
                                    <td><input type="checkbox" :checked="w.accepted" class="accent-brand-500" :title="w.accepted ? 'Reject' : 'Accept'" @change="toggle(w.index)" /></td>
                                    <td class="text-[11.5px]">{{ reasonLabel(w) }}<span v-if="overrides[String(w.index)]" class="text-accent-500 ml-1">(override)</span></td>
                                    <td class="num">{{ fmtNum(w.sta_lta_max) }}</td>
                                    <td class="num">{{ fmtNum(w.sta_lta_min) }}</td>
                                    <td class="num">{{ fmtNum(w.amp_ratio) }}</td>
                                    <td v-if="isCustom()"><Button icon size="xs" variant="ghost" title="Delete this window" @click="deleteWindow(w)"><X class="size-3.5" /></Button></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </Panel>

                <div class="space-y-4">
                    <SeismogramPlayer :recording-id="rid" :run-id="ctl.runId" :fs="fs" :duration="recording.duration_s ?? null" :channels="recording.meta?.channels" @time="cursor = $event" @bookmark="addBookmark" />
                    <Panel title="Bookmarks" :padded="false">
                        <template #actions>
                            <Button size="xs" :disabled="!bookmarks.length || !result" title="Reject every accepted window that contains a bookmark" @click="rejectBookmarked">Reject bookmarked windows</Button>
                        </template>
                        <p v-if="!bookmarks.length" class="p-3 text-[12px] text-faint">No bookmarks. Play the signal and press <span class="num">B</span> (or Bookmark) when you hear a transient.</p>
                        <ul v-else class="max-h-40 overflow-auto scroll-thin divide-y divide-[var(--ui-border)]">
                            <li v-for="(b, i) in bookmarks" :key="i" class="flex items-center gap-2 px-3 py-1.5 text-[12px]">
                                <span class="size-2 rounded-full bg-[#00d5ff]" /><span class="num">B{{ i + 1 }} · {{ fmtNum(b, 5) }} s</span>
                                <Badge v-if="result?.windows.some((w) => w.accepted && b >= w.start_s && b <= w.end_s)" tone="warn">in accepted window</Badge>
                                <button class="ml-auto text-faint hover:text-bad-500" title="Remove" @click="removeBookmark(i)"><X class="size-3.5" /></button>
                            </li>
                        </ul>
                    </Panel>
                </div>
            </div>
            <div class="flex justify-end pt-1">
                <Button variant="primary" size="lg" :disabled="!result" @click="goHvsr">Next step: HVSR analysis <ArrowRight class="size-4" /></Button>
            </div>
        </template>
    </div>
</template>
