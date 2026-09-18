import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useProjectStore } from '@/stores/project';

export interface Crumb { label: string; to: string | null }
export type StepKey = 'waveforms' | 'windows' | 'hvsr';

/**
 * Hierarchical navigation context for the current route:
 * breadcrumb, hierarchical parent ("Back" target) and the recording step switcher.
 * Never relies on browser history, so "Back" always goes one level up.
 */
export function useNavigation() {
    const route = useRoute();
    const store = useProjectStore();

    const projectId = computed<string | null>(() => {
        if (typeof route.params.p === 'string') return route.params.p;
        return store.current?.id ?? null;
    });
    const recordingId = computed<string | null>(() => {
        if (typeof route.params.r === 'string') return route.params.r;
        if (typeof route.params.a === 'string') return store.analysis(route.params.a)?.recording_id ?? null;
        return null;
    });
    const analysisId = computed<string | null>(() => (typeof route.params.a === 'string' ? route.params.a : null));
    const runId = computed<string | null>(() => {
        if (typeof route.query.run === 'string' && route.query.run) return route.query.run;
        if (analysisId.value) return store.analysis(analysisId.value)?.processing_run_id ?? null;
        return null;
    });
    const recording = computed(() => (recordingId.value ? store.recording(recordingId.value) : undefined));
    const analysis = computed(() => (analysisId.value ? store.analysis(analysisId.value) : undefined));
    const section = computed(() => (route.meta.section as string | undefined) ?? '');

    const step = computed<StepKey | null>(() => {
        if (section.value === 'waveforms' || section.value === 'windows' || section.value === 'hvsr') return section.value;
        return null;
    });

    function stepRoute(kind: StepKey, rid?: string | null, run?: string | null): string {
        const id = rid ?? recordingId.value;
        if (!id) return '/projects';
        const q = run ?? runId.value;
        return `/recordings/${id}/${kind}${q ? `?run=${q}` : ''}`;
    }

    const crumbs = computed<Crumb[]>(() => {
        const out: Crumb[] = [{ label: 'Projects', to: '/projects' }];
        const p = store.current;
        if (p && (projectId.value === p.id)) out.push({ label: p.name, to: `/projects/${p.id}` });
        if (recording.value) out.push({ label: recording.value.name, to: stepRoute('waveforms', recording.value.id, null) });
        if (analysis.value) out.push({ label: analysis.value.name, to: null });
        return out;
    });

    /** Hierarchical parent of the current page. */
    const parent = computed<{ label: string; to: string } | null>(() => {
        const p = store.current;
        switch (section.value) {
            case 'projects':
                return route.name === 'project' ? { label: 'Projects', to: '/projects' } : null;
            case 'import': case 'compare': case 'reports':
                return p ? { label: p.name, to: `/projects/${p.id}` } : { label: 'Projects', to: '/projects' };
            case 'waveforms':
                return p ? { label: p.name, to: `/projects/${p.id}` } : { label: 'Projects', to: '/projects' };
            case 'windows':
                return recordingId.value ? { label: 'Waveforms', to: stepRoute('waveforms') } : { label: 'Projects', to: '/projects' };
            case 'hvsr':
                if (analysisId.value && recordingId.value) return { label: 'HVSR analysis', to: stepRoute('hvsr') };
                return recordingId.value ? { label: 'Windows', to: stepRoute('windows') } : { label: 'Projects', to: '/projects' };
            case 'manual': case 'settings':
                return p ? { label: p.name, to: `/projects/${p.id}` } : { label: 'Projects', to: '/projects' };
            default:
                return null;
        }
    });

    return { projectId, recordingId, analysisId, runId, recording, analysis, section, step, stepRoute, crumbs, parent };
}
