export class ApiError extends Error {
    status: number;
    errors: Record<string, string[]> | null;
    payload: unknown;

    constructor(status: number, message: string, errors: Record<string, string[]> | null = null, payload: unknown = null) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.errors = errors;
        this.payload = payload;
    }

    get isEngineDown(): boolean {
        return this.status === 503;
    }

    get hint(): string | null {
        const p = this.payload as { hint?: string } | null;
        return p && typeof p.hint === 'string' ? p.hint : null;
    }
}

const BASE = '/api';

async function parse(res: Response): Promise<unknown> {
    const text = await res.text();
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch {
        return { message: text.slice(0, 500) };
    }
}

async function request<T>(method: string, path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    let payload: BodyInit | undefined;
    if (body instanceof FormData) {
        payload = body;
    } else if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
    }
    let res: Response;
    try {
        res = await fetch(BASE + path, { method, headers, body: payload, ...init });
    } catch (e) {
        throw new ApiError(0, 'Cannot reach the application server. Is the launcher running?', null, { cause: String(e) });
    }
    const data = await parse(res);
    if (!res.ok) {
        const d = (data ?? {}) as { message?: string; errors?: Record<string, string[]> };
        const msg = d.message || `${res.status} ${res.statusText}`;
        throw new ApiError(res.status, msg, d.errors ?? null, data);
    }
    return data as T;
}

export const http = {
    get: <T>(path: string) => request<T>('GET', path),
    post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
    put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
    delete: <T>(path: string) => request<T>('DELETE', path),
};

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v === null || v === undefined || v === '') continue;
        p.set(k, String(v));
    }
    const s = p.toString();
    return s ? `?${s}` : '';
}

export function apiUrl(path: string): string {
    return BASE + path;
}

/** Trigger a browser download of an API file endpoint (works offline, same origin). */
export async function downloadFile(path: string, filename?: string): Promise<void> {
    const res = await fetch(BASE + path, { headers: { Accept: '*/*' } });
    if (!res.ok) {
        const data = await parse(res);
        const d = (data ?? {}) as { message?: string };
        throw new ApiError(res.status, d.message || `${res.status} ${res.statusText}`, null, data);
    }
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
    const name = filename || (m ? decodeURIComponent(m[1]) : 'download');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
}
