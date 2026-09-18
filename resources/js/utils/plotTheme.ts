import type { Layout, Config } from 'plotly.js';

export const BRAND = {
    navy: '#2f3238',
    navyLight: '#e6e8ee',
    orange: '#F26522',
    n: '#2f6fb0',
    e: '#2f8f5b',
    z: '#8b5cf6',
    h: '#2f3238',
    accepted: 'rgba(47,143,91,0.18)',
    rejected: 'rgba(201,70,61,0.20)',
    band: 'rgba(58,60,65,0.16)',
    bandDark: 'rgba(230,232,238,0.18)',
    windowLine: 'rgba(120,125,140,0.35)',
};

export function componentColor(c: 'n' | 'e' | 'z' | 'h', dark: boolean): string {
    if (c === 'h') return dark ? BRAND.navyLight : BRAND.navy;
    return BRAND[c];
}

export function baseLayout(dark: boolean, overrides: Partial<Layout> = {}): Partial<Layout> {
    const text = dark ? '#e6e8ee' : '#1b1d24';
    const muted = dark ? '#a4aab7' : '#5c6270';
    const grid = dark ? '#2c303a' : '#e6e8ed';
    const bg = dark ? '#1c1f27' : '#ffffff';
    const axis = {
        gridcolor: grid,
        zerolinecolor: grid,
        linecolor: grid,
        tickfont: { color: muted, size: 11 },
        title: { font: { color: muted, size: 13 }, standoff: 8 },
        automargin: true,
    };
    const layout: Partial<Layout> = {
        paper_bgcolor: bg,
        plot_bgcolor: bg,
        font: { family: "'Inter Variable', system-ui, sans-serif", color: text, size: 12 },
        margin: { l: 56, r: 16, t: 64, b: 44 },
        hovermode: 'closest',
        hoverlabel: { bgcolor: dark ? '#232732' : '#ffffff', bordercolor: grid, font: { color: text, size: 11, family: "'JetBrains Mono Variable', monospace" } },
        legend: { bgcolor: 'rgba(0,0,0,0)', font: { color: muted, size: 11 }, orientation: 'h', x: 0, xanchor: 'left', y: 1.0, yanchor: 'bottom' },
        xaxis: { ...axis },
        yaxis: { ...axis },
        ...overrides,
    };
    return layout;
}

export const baseConfig: Partial<Config> = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toImage'],
    displayModeBar: true,
    doubleClick: 'reset',
};
