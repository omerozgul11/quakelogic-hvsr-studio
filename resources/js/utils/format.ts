export function fmtNum(v: number | null | undefined, sig = 3): string {
    if (v === null || v === undefined || Number.isNaN(v)) return '—';
    if (v === 0) return '0';
    const a = Math.abs(v);
    if (a >= 1e5 || a < 1e-3) return v.toExponential(sig - 1);
    const digits = Math.max(0, sig - 1 - Math.floor(Math.log10(a)));
    return v.toFixed(Math.min(digits, 6)).replace(/\.?0+$/, '');
}

export function fmtHz(v: number | null | undefined): string {
    return v === null || v === undefined || Number.isNaN(v) ? '—' : `${fmtNum(v, 4)} Hz`;
}

export function fmtDuration(seconds: number | null | undefined): string {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '—';
    const s = Math.round(seconds);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    if (h > 0) return `${h} h ${m} min ${r} s`;
    if (m > 0) return `${m} min ${r} s`;
    return `${fmtNum(seconds, 4)} s`;
}

export function fmtBytes(b: number | null | undefined): string {
    if (b === null || b === undefined) return '—';
    const units = ['B', 'kB', 'MB', 'GB'];
    let i = 0;
    let v = b;
    while (v >= 1024 && i < units.length - 1) {
        v /= 1024;
        i++;
    }
    return `${i === 0 ? v : v.toFixed(1)} ${units[i]}`;
}

export function fmtDate(iso: string | null | undefined): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export function fmtUtc(iso: string | null | undefined): string {
    if (!iso) return '—';
    return iso.replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/Z$/, '') + ' UTC';
}

export function shortId(id: string | null | undefined, n = 8): string {
    return id ? id.slice(0, n) : '—';
}

export function pct(v: number | null | undefined): string {
    return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;
}

export function titleCase(s: string): string {
    return s.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
