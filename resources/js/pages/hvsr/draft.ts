import type { HvsrParams, WindowOverrides } from '@/api/types';
import { mergeHvsrParams } from '@/components/processing/defaults';

export interface HvsrDraft { params: HvsrParams; overrides: WindowOverrides; runId: string | null }

const key = (rid: string) => `hvsr-draft:${rid}`;

export function loadDraft(rid: string): HvsrDraft | null {
    try {
        const raw = sessionStorage.getItem(key(rid));
        if (!raw) return null;
        const d = JSON.parse(raw) as Partial<HvsrDraft>;
        return { params: mergeHvsrParams(d.params), overrides: d.overrides ?? {}, runId: d.runId ?? null };
    } catch { return null; }
}
export function saveDraft(rid: string, d: HvsrDraft): void {
    try { sessionStorage.setItem(key(rid), JSON.stringify(d)); } catch { /* ignore */ }
}
