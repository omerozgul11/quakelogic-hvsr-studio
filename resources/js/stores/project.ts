import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from '@/api';
import type { Analysis, Preset, Project, ProcessingRun, Recording, Station, Ulid } from '@/api/types';

export const useProjectStore = defineStore('project', () => {
    const projects = ref<Project[]>([]);
    const current = ref<Project | null>(null);
    const loading = ref(false);
    const error = ref<string | null>(null);

    const stations = computed<Station[]>(() => current.value?.stations ?? []);
    const recordings = computed<Recording[]>(() => current.value?.recordings ?? []);
    const presets = computed<Preset[]>(() => current.value?.presets ?? []);
    const analyses = computed<Analysis[]>(() => recordings.value.flatMap((r) => r.analyses ?? []));
    const runs = computed<ProcessingRun[]>(() => recordings.value.flatMap((r) => r.runs ?? []));

    async function loadList() {
        projects.value = await api.projects.list();
    }

    async function open(id: Ulid, force = false): Promise<Project> {
        if (!force && current.value && current.value.id === id) return current.value;
        loading.value = true;
        error.value = null;
        try {
            current.value = await api.projects.get(id);
            return current.value;
        } catch (e) {
            error.value = (e as Error).message;
            throw e;
        } finally {
            loading.value = false;
        }
    }

    async function refresh() {
        if (current.value) await open(current.value.id, true);
    }

    function recording(id: Ulid): Recording | undefined {
        return recordings.value.find((r) => r.id === id);
    }
    function analysis(id: Ulid): Analysis | undefined {
        return analyses.value.find((a) => a.id === id);
    }
    function station(id: Ulid | null | undefined): Station | undefined {
        return id ? stations.value.find((s) => s.id === id) : undefined;
    }
    function recordingsForStation(stationId: Ulid | null): Recording[] {
        return recordings.value.filter((r) => (r.station_id ?? null) === stationId);
    }

    /** Ensure the project owning a recording/analysis is loaded (deep-link support). */
    async function ensureForRecording(recordingId: Ulid): Promise<Recording> {
        const existing = recording(recordingId);
        if (existing) return existing;
        const rec = await api.recordings.get(recordingId);
        if (rec.project_id) await open(rec.project_id, true);
        return recording(recordingId) ?? rec;
    }
    async function ensureForAnalysis(analysisId: Ulid): Promise<Analysis> {
        const existing = analysis(analysisId);
        if (existing) return existing;
        const a = await api.analyses.get(analysisId, false);
        if (a.project_id) await open(a.project_id, true);
        return a;
    }

    function close() {
        current.value = null;
    }

    return {
        projects, current, loading, error, stations, recordings, presets, analyses, runs,
        loadList, open, refresh, recording, analysis, station, recordingsForStation, ensureForRecording, ensureForAnalysis, close,
    };
});
