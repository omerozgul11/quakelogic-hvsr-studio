import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from '@/api';
import type { Job, JobStatus } from '@/api/types';

export interface TrackedJob {
    key: string;
    label: string;
    kind: 'run' | 'analysis' | 'report' | 'batch' | 'other';
    status: JobStatus;
    progress: number;
    message: string | null;
    error: string | null;
    /** Poll function returns the latest status. */
    poll: () => Promise<{ status: JobStatus; progress: number; message?: string | null; error?: string | null }>;
    cancel?: () => Promise<void>;
    onDone?: (status: JobStatus) => void;
    startedAt: number;
    finishedAt: number | null;
}

const ACTIVE: JobStatus[] = ['queued', 'running'];

export const useJobsStore = defineStore('jobs', () => {
    const jobs = ref<TrackedJob[]>([]);
    let timer: number | null = null;

    const active = computed(() => jobs.value.filter((j) => ACTIVE.includes(j.status)));
    const recent = computed(() => jobs.value.filter((j) => !ACTIVE.includes(j.status)).slice(-5));

    function ensureTimer() {
        if (timer !== null) return;
        timer = window.setInterval(tick, 1000);
    }

    async function tick() {
        const list = active.value;
        if (list.length === 0) {
            if (timer !== null) { window.clearInterval(timer); timer = null; }
            return;
        }
        await Promise.all(list.map(async (j) => {
            try {
                const s = await j.poll();
                j.status = s.status;
                j.progress = s.progress ?? j.progress;
                j.message = s.message ?? j.message;
                j.error = s.error ?? null;
                if (!ACTIVE.includes(s.status)) {
                    j.finishedAt = Date.now();
                    j.onDone?.(s.status);
                }
            } catch (e) {
                // Transient poll failures are ignored; a dead server will surface elsewhere.
                j.message = (e as Error).message;
            }
        }));
    }

    function track(job: Omit<TrackedJob, 'status' | 'progress' | 'message' | 'error' | 'startedAt' | 'finishedAt'> & Partial<Pick<TrackedJob, 'status' | 'progress'>>): TrackedJob {
        const existing = jobs.value.find((j) => j.key === job.key);
        if (existing) {
            existing.poll = job.poll;
            existing.onDone = job.onDone;
            existing.cancel = job.cancel;
            if (!ACTIVE.includes(existing.status)) {
                existing.status = job.status ?? 'queued';
                existing.progress = job.progress ?? 0;
                existing.finishedAt = null;
                existing.startedAt = Date.now();
            }
            ensureTimer();
            return existing;
        }
        const t: TrackedJob = {
            ...job,
            status: job.status ?? 'queued',
            progress: job.progress ?? 0,
            message: null,
            error: null,
            startedAt: Date.now(),
            finishedAt: null,
        };
        jobs.value.push(t);
        if (jobs.value.length > 30) jobs.value.splice(0, jobs.value.length - 30);
        ensureTimer();
        return t;
    }

    /** Track a raw engine job id through GET /api/jobs/{id}. */
    function trackEngineJob(jobId: string, label: string, kind: TrackedJob['kind'], onDone?: (s: JobStatus) => void) {
        return track({
            key: `job:${jobId}`,
            label,
            kind,
            poll: async () => {
                const j: Job = await api.app.job(jobId);
                return { status: j.status, progress: j.progress, message: j.message, error: j.error };
            },
            onDone,
        });
    }

    async function cancel(key: string) {
        const j = jobs.value.find((x) => x.key === key);
        if (j?.cancel) await j.cancel();
    }
    function dismiss(key: string) {
        jobs.value = jobs.value.filter((j) => j.key !== key);
    }
    function isActive(key: string): boolean {
        const j = jobs.value.find((x) => x.key === key);
        return !!j && ACTIVE.includes(j.status);
    }

    return { jobs, active, recent, track, trackEngineJob, cancel, dismiss, isActive };
});
