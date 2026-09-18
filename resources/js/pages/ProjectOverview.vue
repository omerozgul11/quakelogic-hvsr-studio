<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter, RouterLink } from 'vue-router';
import { Upload, Plus, Trash2, Check, X, Pencil, Waves, BarChart3, Layers, FileText } from 'lucide-vue-next';
import { api } from '@/api';
import type { Station, Recording } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import { useUnits } from '@/composables/useUnits';
import Button from '@/components/ui/Button.vue';
import Panel from '@/components/ui/Panel.vue';
import Badge from '@/components/ui/Badge.vue';
import StatusDot from '@/components/ui/StatusDot.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import PageHeader from '@/components/PageHeader.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import Modal from '@/components/ui/Modal.vue';
import { fmtDate, fmtDuration, fmtNum, fmtHz } from '@/utils/format';

const route = useRoute();
const router = useRouter();
const store = useProjectStore();
const toast = useToastStore();
const unitsUi = useUnits();
const pid = computed(() => String(route.params.p));
const error = ref<unknown>(null);

onMounted(async () => {
    try { await store.open(pid.value, true); } catch (e) { error.value = e; }
});

// --- stations inline editing ---
type Draft = { code: string; name: string; latitude: number | null; longitude: number | null; elevation: number | null; orientation_deg: number | null; notes: string };
const editing = ref<string | null>(null);
const draft = ref<Draft>(blank());
const adding = ref(false);
function blank(): Draft { return { code: '', name: '', latitude: null, longitude: null, elevation: null, orientation_deg: 0, notes: '' }; }
function startEdit(s: Station) {
    editing.value = s.id;
    draft.value = { code: s.code, name: s.name ?? '', latitude: s.latitude ?? null, longitude: s.longitude ?? null, elevation: s.elevation ?? null, orientation_deg: s.orientation_deg ?? 0, notes: s.notes ?? '' };
}
async function saveStation() {
    try {
        if (editing.value) await api.stations.update(editing.value, draft.value);
        else await api.stations.create(pid.value, draft.value);
        editing.value = null; adding.value = false;
        await store.refresh();
        toast.success('Station saved');
    } catch (e) { toast.error('Could not save station', (e as Error).message); }
}
const confirmStation = ref<Station | null>(null);
async function deleteStation() {
    if (!confirmStation.value) return;
    try { await api.stations.remove(confirmStation.value.id); confirmStation.value = null; await store.refresh(); } catch (e) { toast.error('Could not delete station', (e as Error).message); }
}
const confirmRecording = ref<Recording | null>(null);
async function deleteRecording() {
    if (!confirmRecording.value) return;
    try { await api.recordings.remove(confirmRecording.value.id); confirmRecording.value = null; await store.refresh(); toast.success('Recording deleted'); } catch (e) { toast.error('Could not delete recording', (e as Error).message); }
}

const recentAnalyses = computed(() => [...store.analyses].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? '')).slice(0, 8));
function validationTone(r: Recording): 'ok' | 'warn' | 'bad' | 'neutral' {
    const issues = r.validation?.issues ?? [];
    if (r.status === 'invalid' || issues.some((i) => i.severity === 'error')) return 'bad';
    if (issues.some((i) => i.severity === 'warning')) return 'warn';
    return r.status === 'ready' ? 'ok' : 'neutral';
}
function validationLabel(r: Recording): string {
    const issues = r.validation?.issues ?? [];
    const w = issues.filter((i) => i.severity === 'warning').length;
    const e = issues.filter((i) => i.severity === 'error').length;
    if (e) return `${e} error${e > 1 ? 's' : ''}`;
    if (w) return `${w} warning${w > 1 ? 's' : ''}`;
    return 'valid';
}
</script>

<template>
    <div class="p-6 max-w-7xl space-y-5">
        <ErrorBanner v-if="error" :error="error" />
        <template v-else-if="store.current">
            <PageHeader :title="store.current.name">
                <template #subtitle>{{ store.current.description || 'No description.' }} <span class="text-faint">· Folder <span class="num">{{ store.current.folder }}</span></span></template>
                <template #actions><Button variant="primary" @click="router.push(`/projects/${pid}/import`)"><Upload class="size-4" />Import recordings</Button></template>
            </PageHeader>

            <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
                <RouterLink :to="`/projects/${pid}/import`" class="card p-4 flex items-center gap-3 hover:-translate-y-px transition"><span class="grid place-items-center size-9 rounded-xl bg-brand-500/12 text-brand-700 dark:text-brand-300"><Upload class="size-4" /></span><span><span class="block font-medium text-[13px]">Import</span><span class="block text-[11.5px] text-muted">TXT, CSV, MiniSEED</span></span></RouterLink>
                <RouterLink :to="store.recordings[0] ? `/recordings/${store.recordings[0].id}/waveforms` : `/projects/${pid}/import`" class="card p-4 flex items-center gap-3 hover:-translate-y-px transition"><span class="grid place-items-center size-9 rounded-xl bg-brand-500/12 text-brand-700 dark:text-brand-300"><Waves class="size-4" /></span><span><span class="block font-medium text-[13px]">Waveforms</span><span class="block text-[11.5px] text-muted">Filters, detrend, spectra</span></span></RouterLink>
                <RouterLink :to="`/projects/${pid}/compare`" class="card p-4 flex items-center gap-3 hover:-translate-y-px transition"><span class="grid place-items-center size-9 rounded-xl bg-brand-500/12 text-brand-700 dark:text-brand-300"><Layers class="size-4" /></span><span><span class="block font-medium text-[13px]">Batch & compare</span><span class="block text-[11.5px] text-muted">Presets across stations</span></span></RouterLink>
                <RouterLink :to="`/projects/${pid}/reports`" class="card p-4 flex items-center gap-3 hover:-translate-y-px transition"><span class="grid place-items-center size-9 rounded-xl bg-brand-500/12 text-brand-700 dark:text-brand-300"><FileText class="size-4" /></span><span><span class="block font-medium text-[13px]">Reports</span><span class="block text-[11.5px] text-muted">PDF, CSV, JSON</span></span></RouterLink>
            </div>

            <Panel title="Stations" :padded="false">
                <template #actions><Button size="sm" @click="adding = true; editing = null; draft = blank()"><Plus class="size-3.5" />Add station</Button></template>
                <table class="table hover">
                    <thead><tr><th>Code</th><th>Name</th><th>Latitude</th><th>Longitude</th><th>Elevation ({{ unitsUi.lengthLabel }})</th><th>N azimuth (°)</th><th>Recordings</th><th></th></tr></thead>
                    <tbody>
                        <tr v-if="adding">
                            <td><input v-model="draft.code" class="input" placeholder="STA1" /></td>
                            <td><input v-model="draft.name" class="input" /></td>
                            <td><input v-model.number="draft.latitude" class="input num" type="number" step="any" /></td>
                            <td><input v-model.number="draft.longitude" class="input num" type="number" step="any" /></td>
                            <td><input :value="unitsUi.lengthToDisplay(draft.elevation)" class="input num" type="number" step="any" :title="`Elevation in ${unitsUi.lengthLabel}; stored in metres`" @input="draft.elevation = unitsUi.lengthFromDisplay(parseFloat(($event.target as HTMLInputElement).value))" /></td>
                            <td><input v-model.number="draft.orientation_deg" class="input num" type="number" step="any" /></td>
                            <td></td>
                            <td class="whitespace-nowrap"><button class="p-1 text-ok-500" title="Save" @click="saveStation"><Check class="size-4" /></button><button class="p-1 text-faint" title="Cancel" @click="adding = false"><X class="size-4" /></button></td>
                        </tr>
                        <tr v-for="s in store.stations" :key="s.id">
                            <template v-if="editing === s.id">
                                <td><input v-model="draft.code" class="input" /></td>
                                <td><input v-model="draft.name" class="input" /></td>
                                <td><input v-model.number="draft.latitude" class="input num" type="number" step="any" /></td>
                                <td><input v-model.number="draft.longitude" class="input num" type="number" step="any" /></td>
                                <td><input :value="unitsUi.lengthToDisplay(draft.elevation)" class="input num" type="number" step="any" :title="`Elevation in ${unitsUi.lengthLabel}; stored in metres`" @input="draft.elevation = unitsUi.lengthFromDisplay(parseFloat(($event.target as HTMLInputElement).value))" /></td>
                                <td><input v-model.number="draft.orientation_deg" class="input num" type="number" step="any" /></td>
                                <td class="num">{{ store.recordingsForStation(s.id).length }}</td>
                                <td class="whitespace-nowrap"><button class="p-1 text-ok-500" title="Save" @click="saveStation"><Check class="size-4" /></button><button class="p-1 text-faint" title="Cancel" @click="editing = null"><X class="size-4" /></button></td>
                            </template>
                            <template v-else>
                                <td class="font-medium">{{ s.code }}</td>
                                <td>{{ s.name || '—' }}</td>
                                <td class="num">{{ fmtNum(s.latitude, 6) }}</td>
                                <td class="num">{{ fmtNum(s.longitude, 6) }}</td>
                                <td class="num">{{ fmtNum(unitsUi.lengthToDisplay(s.elevation), 5) }}</td>
                                <td class="num">{{ fmtNum(s.orientation_deg, 4) }}</td>
                                <td class="num">{{ store.recordingsForStation(s.id).length }}</td>
                                <td class="whitespace-nowrap"><button class="p-1 text-faint hover:text-ui" title="Edit" @click="startEdit(s)"><Pencil class="size-3.5" /></button><button class="p-1 text-faint hover:text-bad-500" title="Delete" @click="confirmStation = s"><Trash2 class="size-3.5" /></button></td>
                            </template>
                        </tr>
                        <tr v-if="store.stations.length === 0 && !adding"><td colspan="8" class="text-faint text-center py-4">No stations. Stations are optional; recordings can also be imported unassigned.</td></tr>
                    </tbody>
                </table>
            </Panel>

            <Panel title="Recordings" :padded="false">
                <EmptyState v-if="store.recordings.length === 0" title="No recordings" description="Import TXT, CSV or MiniSEED files to create the first three-component recording." :icon="Upload">
                    <Button variant="primary" @click="router.push(`/projects/${pid}/import`)">Import recordings</Button>
                </EmptyState>
                <table v-else class="table hover">
                    <thead><tr><th></th><th>Name</th><th>Station</th><th>Format</th><th>Rate</th><th>Duration</th><th>Start (UTC)</th><th>Validation</th><th>Runs</th><th>Analyses</th><th></th></tr></thead>
                    <tbody>
                        <tr v-for="r in store.recordings" :key="r.id">
                            <td><StatusDot :status="r.status" /></td>
                            <td><RouterLink :to="`/recordings/${r.id}/waveforms`" class="font-medium hover:underline">{{ r.name }}</RouterLink><Badge v-if="r.is_synthetic" tone="accent" class="ml-1.5">synthetic</Badge></td>
                            <td>{{ store.station(r.station_id)?.code ?? '—' }}</td>
                            <td class="uppercase text-[11px]">{{ r.format }}</td>
                            <td class="num">{{ fmtHz(r.sample_rate) }}</td>
                            <td class="num">{{ fmtDuration(r.duration_s) }}</td>
                            <td class="num text-[11.5px]">{{ r.start_time ?? '—' }}</td>
                            <td><Badge :tone="validationTone(r)">{{ validationLabel(r) }}</Badge></td>
                            <td class="num">{{ r.runs?.length ?? 0 }}</td>
                            <td class="num">{{ r.analyses?.length ?? 0 }}</td>
                            <td class="whitespace-nowrap">
                                <RouterLink :to="`/recordings/${r.id}/hvsr`" class="p-1 text-faint hover:text-ui inline-block" title="HVSR analysis"><BarChart3 class="size-3.5" /></RouterLink>
                                <button class="p-1 text-faint hover:text-bad-500" title="Delete" @click="confirmRecording = r"><Trash2 class="size-3.5" /></button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </Panel>

            <Panel title="Recent analyses" :padded="false">
                <table v-if="recentAnalyses.length" class="table hover">
                    <thead><tr><th></th><th>Name</th><th>Recording</th><th>f0</th><th>A0</th><th>Peak</th><th>Windows</th><th>Updated</th></tr></thead>
                    <tbody>
                        <tr v-for="a in recentAnalyses" :key="a.id">
                            <td><StatusDot :status="a.status" /></td>
                            <td><RouterLink :to="`/analyses/${a.id}`" class="font-medium hover:underline">{{ a.name }}</RouterLink></td>
                            <td>{{ store.recording(a.recording_id)?.name ?? '—' }}</td>
                            <td class="num">{{ fmtHz(a.summary?.f0) }}</td>
                            <td class="num">{{ fmtNum(a.summary?.a0) }}</td>
                            <td><Badge :tone="a.summary?.peak_status === 'clear' ? 'ok' : a.summary?.peak_status === 'multiple' ? 'warn' : 'neutral'">{{ a.summary?.peak_status ?? a.status }}</Badge></td>
                            <td class="num">{{ a.summary?.count_accepted ?? '—' }} / {{ a.summary?.count_total ?? '—' }}</td>
                            <td class="text-faint">{{ fmtDate(a.updated_at) }}</td>
                        </tr>
                    </tbody>
                </table>
                <p v-else class="text-faint text-[12.5px] p-4">No analyses yet.</p>
            </Panel>
        </template>

        <Modal :open="!!confirmStation" title="Delete station?" @close="confirmStation = null">
            <p class="text-[13px]">Delete station <strong>{{ confirmStation?.code }}</strong>? Its recordings remain in the project as unassigned.</p>
            <template #footer><Button @click="confirmStation = null">Cancel</Button><Button variant="danger" @click="deleteStation">Delete</Button></template>
        </Modal>
        <Modal :open="!!confirmRecording" title="Delete recording?" @close="confirmRecording = null">
            <p class="text-[13px]">Delete <strong>{{ confirmRecording?.name }}</strong> with all of its processing runs, analyses and exports? Source copies in the project folder are removed too.</p>
            <template #footer><Button @click="confirmRecording = null">Cancel</Button><Button variant="danger" @click="deleteRecording">Delete</Button></template>
        </Modal>
    </div>
</template>
