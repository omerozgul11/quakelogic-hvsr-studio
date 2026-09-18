<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, RouterLink } from 'vue-router';
import { FileText, Download, RefreshCw, ClipboardList } from 'lucide-vue-next';
import SurveyDialog from '@/components/SurveyDialog.vue';
import { api } from '@/api';
import type { Analysis, ExportKind, Survey } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useJobsStore } from '@/stores/jobs';
import { useToastStore } from '@/stores/toast';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import StatusDot from '@/components/ui/StatusDot.vue';
import Dropdown from '@/components/ui/Dropdown.vue';
import MenuItem from '@/components/ui/MenuItem.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import PageHeader from '@/components/PageHeader.vue';
import { fmtHz, fmtNum, fmtDate } from '@/utils/format';

const route = useRoute();
const store = useProjectStore();
const jobs = useJobsStore();
const toast = useToastStore();
const pid = computed(() => String(route.params.p));
const error = ref<unknown>(null);
const busy = ref<Set<string>>(new Set());

onMounted(async () => { try { await store.open(pid.value, true); } catch (e) { error.value = e; } });
const analyses = computed(() => store.analyses.filter((a) => a.status === 'done'));

function setBusy(id: string, v: boolean) { const s = new Set(busy.value); if (v) s.add(id); else s.delete(id); busy.value = s; }
async function generate(a: Analysis) {
    setBusy(a.id, true);
    try {
        await api.analyses.requestReport(a.id);
        jobs.track({
            key: `report:${a.id}`, label: `Report · ${a.name}`, kind: 'report', status: 'queued', progress: 0,
            poll: async () => { const x = await api.analyses.get(a.id, false); return { status: x.report_status ?? 'running', progress: x.report_status === 'done' ? 1 : 0.5, error: x.error }; },
            onDone: async (s) => { setBusy(a.id, false); await store.refresh(); if (s === 'done') { toast.success('Report ready', a.name); await api.analyses.downloadReport(a.id); } else toast.error('Report failed', a.name); },
        });
    } catch (e) { setBusy(a.id, false); toast.error('Could not generate report', (e as Error).message); }
}
const detailsFor = ref<Analysis | null>(null);
function onSurveySaved(sv: Survey) { if (detailsFor.value) detailsFor.value = { ...detailsFor.value, survey: sv }; }
async function download(a: Analysis) { try { await api.analyses.downloadReport(a.id); } catch (e) { toast.error('Download failed', (e as Error).message); } }
async function exp(a: Analysis, k: ExportKind) { try { await api.analyses.download(a.id, k); } catch (e) { toast.error('Export failed', (e as Error).message); } }
</script>

<template>
    <div class="p-6 space-y-5">
        <ErrorBanner v-if="error" :error="error" />
        <PageHeader title="Reports & exports" subtitle="PDF analysis reports and data exports for every completed analysis. Everything is generated locally." />
        <Panel :padded="false">
            <EmptyState v-if="!analyses.length" title="No completed analyses" description="Run an HVSR analysis first; reports and exports appear here." :icon="FileText" />
            <table v-else class="table hover">
                <thead><tr><th></th><th>Analysis</th><th>Recording</th><th>Station</th><th>f0</th><th>A0</th><th>Peak</th><th>Report</th><th>Updated</th><th></th></tr></thead>
                <tbody>
                    <tr v-for="a in analyses" :key="a.id">
                        <td><StatusDot :status="a.status" /></td>
                        <td><RouterLink :to="`/analyses/${a.id}`" class="font-medium hover:underline">{{ a.name }}</RouterLink></td>
                        <td>{{ store.recording(a.recording_id)?.name ?? '' }}</td>
                        <td>{{ store.station(store.recording(a.recording_id)?.station_id)?.code ?? '—' }}</td>
                        <td class="num whitespace-nowrap">{{ fmtHz(a.summary?.f0) }}</td>
                        <td class="num">{{ fmtNum(a.summary?.a0) }}</td>
                        <td><Badge :tone="a.summary?.peak_status === 'clear' ? 'ok' : a.summary?.peak_status === 'multiple' ? 'warn' : 'neutral'">{{ a.summary?.peak_status ?? '—' }}</Badge></td>
                        <td><Badge :tone="a.report_status === 'done' ? 'ok' : a.report_status === 'failed' ? 'bad' : 'neutral'">{{ a.report_status ?? 'not generated' }}</Badge></td>
                        <td class="text-faint whitespace-nowrap">{{ fmtDate(a.updated_at) }}</td>
                        <td class="whitespace-nowrap">
                            <div class="flex items-center gap-1 justify-end">
                                <Button size="sm" variant="ghost" title="Survey, place, photos and notes printed in the report" @click="detailsFor = a"><ClipboardList class="size-3.5" />Details</Button>
                                <Button v-if="a.report_status === 'done'" size="sm" @click="download(a)"><Download class="size-3.5" />PDF</Button>
                                <Button size="sm" :variant="a.report_status === 'done' ? 'ghost' : 'primary'" :loading="busy.has(a.id) || jobs.isActive(`report:${a.id}`)" :title="a.report_status === 'done' ? 'Regenerate' : 'Generate PDF report'" @click="generate(a)"><component :is="a.report_status === 'done' ? RefreshCw : FileText" class="size-3.5" />{{ a.report_status === 'done' ? '' : 'Generate' }}</Button>
                                <Dropdown label="Exports" title="CSV and JSON exports always use the original SI / raw units">
                                    <MenuItem @click="exp(a, 'hvsr-csv')">H/V curves (CSV)</MenuItem>
                                    <MenuItem @click="exp(a, 'windows-csv')">Window curves (CSV)</MenuItem>
                                    <MenuItem @click="exp(a, 'spectra-csv')">Component spectra (CSV)</MenuItem>
                                    <MenuItem @click="exp(a, 'summary-csv')">Summary (CSV)</MenuItem>
                                    <MenuItem @click="exp(a, 'summary-json')">Summary (JSON)</MenuItem>
                                    <MenuItem @click="exp(a, 'config-json')">Configuration (JSON)</MenuItem>
                                    <MenuItem @click="exp(a, 'azimuthal-csv')">Azimuthal (CSV)</MenuItem>
                                    <MenuItem @click="exp(a, 'geopsy-hv')">Geopsy .hv curve</MenuItem>
                                    <MenuItem @click="exp(a, 'windows-json')">Window set (JSON)</MenuItem>
                                </Dropdown>
                            </div>
                        </td>
                    </tr>
                </tbody>
            </table>
        </Panel>
        <SurveyDialog v-if="detailsFor" :open="!!detailsFor" :analysis-id="detailsFor.id" :recording="store.recording(detailsFor.recording_id) ?? null" :survey="detailsFor.survey ?? null" :generating="busy.has(detailsFor.id)" @close="detailsFor = null" @saved="onSurveySaved" @generate="(a => { detailsFor = null; generate(a); })(detailsFor)" />
    </div>
</template>
