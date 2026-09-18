<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';
import { FolderOpen, Upload, Waves, Grid2x2, BarChart3, Layers, FileText, Settings, BookOpen, ChevronRight, ChevronDown, Search, Plus, Cpu, AudioLines } from 'lucide-vue-next';
import { useProjectStore } from '@/stores/project';
import { useNavigation } from '@/composables/useNavigation';
import StatusDot from '@/components/ui/StatusDot.vue';
import type { Recording } from '@/api/types';
import { fmtNum } from '@/utils/format';

const project = useProjectStore();
const route = useRoute();
const router = useRouter();
const nav = useNavigation();
const pid = computed(() => project.current?.id ?? null);
const section = computed(() => (route.meta.section as string) ?? '');
const hasRecordings = computed(() => project.recordings.length > 0);

interface Item { key: string; label: string; icon: typeof FolderOpen; to: string; enabled: boolean; why?: string }
interface Group { title: string; items: Item[] }

const currentRid = computed(() => nav.recordingId.value ?? project.recordings[0]?.id ?? null);
function stepTo(kind: 'waveforms' | 'windows' | 'hvsr'): string {
    return currentRid.value ? nav.stepRoute(kind, currentRid.value, nav.runId.value) : '/projects';
}
const groups = computed<Group[]>(() => [
    { title: 'Workspace', items: [
        { key: 'projects', label: 'Projects', icon: FolderOpen, to: pid.value ? `/projects/${pid.value}` : '/projects', enabled: true },
        { key: 'import', label: 'Import', icon: Upload, to: pid.value ? `/projects/${pid.value}/import` : '/projects', enabled: !!pid.value, why: 'Open a project first' },
    ] },
    { title: 'Analysis', items: [
        { key: 'waveforms', label: 'Waveforms', icon: Waves, to: stepTo('waveforms'), enabled: hasRecordings.value, why: 'Import a recording first' },
        { key: 'windows', label: 'Windows', icon: Grid2x2, to: stepTo('windows'), enabled: hasRecordings.value, why: 'Import a recording first' },
        { key: 'hvsr', label: 'HVSR', icon: BarChart3, to: stepTo('hvsr'), enabled: hasRecordings.value, why: 'Import a recording first' },
    ] },
    { title: 'Results', items: [
        { key: 'compare', label: 'Batch & compare', icon: Layers, to: pid.value ? `/projects/${pid.value}/compare` : '/projects', enabled: !!pid.value, why: 'Open a project first' },
        { key: 'reports', label: 'Reports', icon: FileText, to: pid.value ? `/projects/${pid.value}/reports` : '/projects', enabled: !!pid.value, why: 'Open a project first' },
    ] },
]);
const bottom: Item[] = [
    { key: 'manual', label: 'User manual', icon: BookOpen, to: '/manual', enabled: true },
    { key: 'settings', label: 'Settings', icon: Settings, to: '/settings', enabled: true },
];

// ---- tree ----
const filter = ref('');
const expanded = ref<string | null>(null);
const runsOpen = ref<Set<string>>(new Set());
const focus = ref<string | null>(null);

watch(() => nav.recordingId.value, (id) => { if (id) expanded.value = id; }, { immediate: true });

const filtered = computed<Recording[]>(() => {
    const q = filter.value.trim().toLowerCase();
    return q ? project.recordings.filter((r) => r.name.toLowerCase().includes(q) || (project.station(r.station_id)?.code ?? '').toLowerCase().includes(q)) : project.recordings;
});
const stationGroups = computed(() => {
    const by = new Map<string | null, Recording[]>();
    for (const r of filtered.value) {
        const k = r.station_id ?? null;
        if (!by.has(k)) by.set(k, []);
        by.get(k)!.push(r);
    }
    const out: { key: string; label: string; recordings: Recording[] }[] = [];
    for (const s of project.stations) if (by.has(s.id)) out.push({ key: s.id, label: s.code + (s.name ? ` · ${s.name}` : ''), recordings: by.get(s.id)! });
    if (by.has(null)) out.push({ key: 'none', label: 'No station', recordings: by.get(null)! });
    return out;
});
const flat = computed(() => stationGroups.value.flatMap((g) => g.recordings.map((r) => r.id)));

function openRecording(r: Recording) {
    expanded.value = expanded.value === r.id && nav.recordingId.value !== r.id ? null : r.id;
    router.push(`/recordings/${r.id}/waveforms`);
}
function toggleExpand(id: string) { expanded.value = expanded.value === id ? null : id; }
function toggleRuns(id: string) { const s = new Set(runsOpen.value); s.has(id) ? s.delete(id) : s.add(id); runsOpen.value = s; }
function onKey(e: KeyboardEvent) {
    const ids = flat.value;
    if (!ids.length) return;
    const i = focus.value ? ids.indexOf(focus.value) : -1;
    if (e.key === 'ArrowDown') { e.preventDefault(); focus.value = ids[Math.min(ids.length - 1, i + 1)] ?? null; }
    else if (e.key === 'ArrowUp') { e.preventDefault(); focus.value = ids[Math.max(0, i - 1)] ?? null; }
    else if (e.key === 'Enter' && focus.value) { const r = project.recording(focus.value); if (r) openRecording(r); }
    else if (e.key === 'ArrowRight' && focus.value) expanded.value = focus.value;
    else if (e.key === 'ArrowLeft' && focus.value) expanded.value = null;
}
function f0Of(a: { summary?: { f0?: number | null } | null }): string | null {
    const f = a.summary?.f0;
    return typeof f === 'number' ? `${fmtNum(f, 3)} Hz` : null;
}
</script>

<template>
    <nav class="flex flex-col min-h-0 h-full">
        <div class="px-3 pt-3 pb-1 space-y-3">
            <div v-for="g in groups" :key="g.title">
                <div class="eyebrow px-2.5 mb-1">{{ g.title }}</div>
                <ul class="space-y-px">
                    <li v-for="it in g.items" :key="it.key">
                        <RouterLink v-if="it.enabled" :to="it.to" class="nav-item" :class="{ active: section === it.key }">
                            <component :is="it.icon" class="size-4 shrink-0 opacity-80" />{{ it.label }}
                        </RouterLink>
                        <span v-else class="nav-item disabled" :title="it.why"><component :is="it.icon" class="size-4 shrink-0" />{{ it.label }}</span>
                    </li>
                </ul>
            </div>
        </div>

        <div class="mx-3 my-2 divider" />

        <div class="flex items-center justify-between px-5 pb-1">
            <span class="eyebrow">Recordings</span>
            <RouterLink v-if="pid" :to="`/projects/${pid}/import`" class="inline-flex items-center gap-1 text-[11.5px] font-medium text-brand-700 hover:underline dark:text-brand-300" title="Import recordings"><Plus class="size-3.5" />Import</RouterLink>
        </div>
        <div v-if="project.current && project.recordings.length > 6" class="px-3 pb-2">
            <div class="relative">
                <Search class="size-3.5 absolute left-2.5 top-2.5 text-faint" />
                <input v-model="filter" type="search" placeholder="Filter recordings" class="input !h-8 !pl-8 !text-[12px] !rounded-lg" />
            </div>
        </div>

        <div class="flex-1 overflow-auto scroll-thin px-2 pb-3" tabindex="0" @keydown="onKey">
            <div v-if="!project.current" class="px-3 py-4 text-center">
                <p class="text-[12px] text-faint mb-3">No project open.</p>
                <RouterLink to="/projects" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand-500/12 text-brand-700 text-[12.5px] font-medium hover:bg-brand-500/20 dark:text-brand-300"><FolderOpen class="size-4" />Open a project</RouterLink>
            </div>
            <div v-else-if="project.recordings.length === 0" class="px-3 py-4 text-center">
                <p class="text-[12px] text-faint mb-3">No recordings yet.</p>
                <RouterLink :to="`/projects/${pid}/import`" class="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand-500/12 text-brand-700 text-[12.5px] font-medium hover:bg-brand-500/20 dark:text-brand-300"><Upload class="size-4" />Import recordings</RouterLink>
            </div>
            <p v-else-if="filtered.length === 0" class="px-3 py-3 text-[12px] text-faint">Nothing matches “{{ filter }}”.</p>
            <template v-for="g in stationGroups" :key="g.key">
                <div class="px-2.5 pt-2 pb-0.5 text-[10.5px] font-semibold uppercase tracking-wider text-faint truncate" :title="g.label">{{ g.label }}</div>
                <div v-for="r in g.recordings" :key="r.id">
                    <div
                        class="tree-row group"
                        :class="{ active: nav.recordingId.value === r.id, focused: focus === r.id }"
                        :title="r.name"
                        @click="openRecording(r)"
                    >
                        <button class="text-faint hover:text-ui -ml-1 p-0.5 rounded" :title="expanded === r.id ? 'Collapse' : 'Expand'" @click.stop="toggleExpand(r.id)">
                            <component :is="expanded === r.id ? ChevronDown : ChevronRight" class="size-3.5" />
                        </button>
                        <AudioLines class="size-4 shrink-0 opacity-70" />
                        <span class="truncate text-[12.5px] font-medium flex-1">{{ r.name }}</span>
                        <span class="quick items-center gap-0.5" @click.stop>
                            <RouterLink :to="nav.stepRoute('waveforms', r.id, null)" class="p-1 rounded hover:bg-black/8 text-faint hover:text-ui" title="Waveforms"><Waves class="size-3.5" /></RouterLink>
                            <RouterLink :to="nav.stepRoute('windows', r.id, null)" class="p-1 rounded hover:bg-black/8 text-faint hover:text-ui" title="Windows"><Grid2x2 class="size-3.5" /></RouterLink>
                            <RouterLink :to="nav.stepRoute('hvsr', r.id, null)" class="p-1 rounded hover:bg-black/8 text-faint hover:text-ui" title="HVSR"><BarChart3 class="size-3.5" /></RouterLink>
                        </span>
                        <StatusDot :status="r.status" class="group-hover:hidden" />
                        <span class="num text-[10.5px] text-faint whitespace-nowrap group-hover:hidden">{{ r.sample_rate ? r.sample_rate + ' Hz' : '' }}</span>
                    </div>
                    <div v-if="expanded === r.id" class="pb-1">
                        <div class="px-2 pl-[30px] pt-1 pb-0.5 text-[11px] text-faint">Analyses ({{ r.analyses?.length ?? 0 }})</div>
                        <p v-if="!(r.analyses?.length)" class="pl-[30px] pr-2 pb-1 text-[11.5px] text-faint">None yet — <RouterLink :to="nav.stepRoute('hvsr', r.id, null)" class="underline hover:text-ui">run HVSR</RouterLink></p>
                        <RouterLink v-for="a in r.analyses ?? []" :key="a.id" :to="`/analyses/${a.id}`" class="tree-sub" :class="{ active: nav.analysisId.value === a.id }" :title="a.name">
                            <BarChart3 class="size-3.5 shrink-0 opacity-70" /><StatusDot :status="a.status" />
                            <span class="truncate flex-1">{{ a.name }}</span>
                            <span v-if="f0Of(a)" class="num text-[10.5px] rounded-full px-1.5 bg-brand-500/12 text-brand-700 dark:text-brand-300 whitespace-nowrap">{{ f0Of(a) }}</span>
                        </RouterLink>
                        <button v-if="r.runs?.length" class="tree-sub w-full text-[11px] text-faint" @click="toggleRuns(r.id)">
                            <component :is="runsOpen.has(r.id) ? ChevronDown : ChevronRight" class="size-3" />Processing runs ({{ r.runs.length }})
                        </button>
                        <template v-if="runsOpen.has(r.id)">
                            <RouterLink v-for="run in r.runs ?? []" :key="run.id" :to="nav.stepRoute('waveforms', r.id, run.id)" class="tree-sub !pl-[42px]" :class="{ active: nav.runId.value === run.id && nav.recordingId.value === r.id }" :title="run.name">
                                <Cpu class="size-3.5 shrink-0 opacity-70" /><StatusDot :status="run.status" /><span class="truncate">{{ run.name }}</span>
                            </RouterLink>
                        </template>
                    </div>
                </div>
            </template>
        </div>

        <div class="mx-3 divider" />
        <ul class="p-3 space-y-px">
            <li v-for="it in bottom" :key="it.key">
                <RouterLink :to="it.to" class="nav-item" :class="{ active: section === it.key }"><component :is="it.icon" class="size-4 shrink-0 opacity-80" />{{ it.label }}</RouterLink>
            </li>
        </ul>
    </nav>
</template>
