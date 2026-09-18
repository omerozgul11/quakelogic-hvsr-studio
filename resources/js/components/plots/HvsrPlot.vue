<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout, PlotMouseEvent, PlotSelectionEvent } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { BRAND } from '@/utils/plotTheme';
import { windowColor } from '@/utils/windowPalette';
import { useAppStore } from '@/stores/app';
import { fmtNum } from '@/utils/format';
import type { CurveSet, PeakCandidate, WindowCurves, ImportedCurve } from '@/api/types';

import { defaultHvsrPlotOptions, type HvsrPlotOptions } from './hvsrPlotOptions';

interface Props {
    frequency: number[];
    curve: CurveSet;
    curveLabel: string;
    windowCurves?: WindowCurves | null;
    /** Legacy prop: same as options.showSingle with grey curves. */
    showWindows?: boolean;
    candidates?: PeakCandidate[];
    selected?: { frequency: number; amplitude: number; source?: string } | null;
    searchRange?: [number, number] | null;
    extra?: { label: string; values: (number | null)[]; color: string; dash?: 'dot' | 'dash' | 'solid' }[];
    loaded?: ImportedCurve[];
    /** Mean smoothed component spectra (linear amplitude) for the dB right axis. */
    spectra?: { h?: (number | null)[] | null; z?: (number | null)[] | null } | null;
    t10?: number | null;
    options?: HvsrPlotOptions;
    height?: number;
    title?: string;
    exportName?: string;
    extraExports?: { label: string; action: () => void | Promise<void> }[];
}
const props = withDefaults(defineProps<Props>(), { showWindows: false, height: 420, exportName: 'hvsr' });
const emit = defineEmits<{ pick: [frequency: number]; selectWindows: [indices: number[]] }>();
const app = useAppStore();
const opt = computed<HvsrPlotOptions>(() => props.options ?? { ...defaultHvsrPlotOptions(), showSingle: props.showWindows });

const toDb = (v: (number | null)[] | null | undefined) => (v ?? []).map((x) => (x === null || x <= 0 ? null : 20 * Math.log10(x)));
/** trace index → window index for box selection */
let traceWindow: number[] = [];

const data = computed<Data[]>(() => {
    const out: Data[] = [];
    traceWindow = [];
    const main = app.isDark ? BRAND.navyLight : BRAND.navy;
    const o = opt.value;
    if (o.showSingle && props.windowCurves) {
        const n = props.windowCurves.curves.length;
        props.windowCurves.curves.forEach((c, i) => {
            if (!props.windowCurves!.accepted[i]) return;
            traceWindow[out.length] = i;
            out.push({
                x: props.windowCurves!.frequency, y: c, type: 'scatter', mode: 'lines', customdata: c.map(() => i),
                line: { color: windowColor(i, n, 0.85), width: 0.9 }, name: `window ${i}`, showlegend: false,
                hovertemplate: `window ${i}<br>f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra></extra>`,
            });
        });
    }
    if (o.stdMode === 'band') {
        out.push({ x: props.frequency, y: props.curve.upper, type: 'scatter', mode: 'lines', line: { width: 0, color: 'rgba(0,0,0,0)' }, name: 'upper', showlegend: false, hoverinfo: 'skip' });
        out.push({ x: props.frequency, y: props.curve.lower, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: app.isDark ? BRAND.bandDark : BRAND.band, line: { width: 0, color: 'rgba(0,0,0,0)' }, name: `Dispersion band: ${props.curve.band}`, hoverinfo: 'skip' });
    } else if (o.stdMode === 'lines') {
        out.push({ x: props.frequency, y: props.curve.upper, type: 'scatter', mode: 'lines', line: { width: 1.2, color: main, dash: 'dash' }, name: `+σ (${props.curve.band})`, hovertemplate: 'f=%{x:.3g} Hz<br>+σ=%{y:.3f}<extra></extra>' });
        out.push({ x: props.frequency, y: props.curve.lower, type: 'scatter', mode: 'lines', line: { width: 1.2, color: main, dash: 'dash' }, name: '−σ', showlegend: false, hovertemplate: 'f=%{x:.3g} Hz<br>−σ=%{y:.3f}<extra></extra>' });
    }
    if (o.showMean) {
        out.push({ x: props.frequency, y: props.curve.values, type: 'scatter', mode: 'lines', line: { color: main, width: 2.4 }, name: props.curveLabel, hovertemplate: 'f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra></extra>' });
    }
    for (const e of props.extra ?? []) {
        out.push({ x: props.frequency, y: e.values, type: 'scatter', mode: 'lines', line: { color: e.color, width: 1.4, dash: e.dash ?? 'dot' }, name: e.label, hovertemplate: 'f=%{x:.3g} Hz<br>%{y:.3f}<extra>' + e.label + '</extra>' });
    }
    if (o.showLoaded) {
        const palette = ['#c026d3', '#0891b2', '#65a30d', '#b45309', '#7c3aed'];
        (props.loaded ?? []).forEach((c, i) => {
            out.push({ x: c.frequency, y: c.values, type: 'scatter', mode: 'lines', line: { color: palette[i % palette.length], width: 1.8, dash: 'dashdot' }, name: `Loaded: ${c.name}`, hovertemplate: 'f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra>' + c.name + '</extra>' });
        });
    }
    if (props.spectra && (o.dbHorizontal || o.dbVertical)) {
        if (o.dbHorizontal && props.spectra.h) out.push({ x: props.frequency, y: toDb(props.spectra.h), type: 'scatter', mode: 'lines', yaxis: 'y2', line: { color: '#c026d3', width: 1.3 }, name: 'H (dB re 1 count)', hovertemplate: 'f=%{x:.3g} Hz<br>H=%{y:.1f} dB<extra></extra>' });
        if (o.dbVertical && props.spectra.z) out.push({ x: props.frequency, y: toDb(props.spectra.z), type: 'scatter', mode: 'lines', yaxis: 'y2', line: { color: '#dc2626', width: 1.3 }, name: 'V (dB re 1 count)', hovertemplate: 'f=%{x:.3g} Hz<br>V=%{y:.1f} dB<extra></extra>' });
    }
    if (props.candidates?.length) {
        out.push({
            x: props.candidates.map((c) => c.frequency), y: props.candidates.map((c) => c.amplitude), type: 'scatter', mode: 'markers', name: 'Candidate peaks',
            marker: { symbol: 'circle-open', size: 9, color: main, line: { width: 1.5 } },
            hovertemplate: '#%{text}<br>f=%{x:.3g} Hz<br>A=%{y:.3f}<extra>candidate</extra>', text: props.candidates.map((c) => String(c.rank)),
        });
    }
    if (props.selected) {
        out.push({
            x: [props.selected.frequency], y: [props.selected.amplitude], type: 'scatter', mode: 'markers', name: `Selected peak (${props.selected.source ?? 'automatic'})`,
            marker: { symbol: 'diamond', size: 12, color: BRAND.orange, line: { width: 1, color: '#fff' } },
            hovertemplate: 'f0=%{x:.3g} Hz<br>A0=%{y:.3f}<extra>selected</extra>',
        });
    }
    return out;
});

const layout = computed<Partial<Layout>>(() => {
    const o = opt.value;
    const shapes: Partial<Layout>['shapes'] = [];
    const annotations: Partial<Layout>['annotations'] = [];
    const fx = (f: number) => (o.freqLog ? Math.log10(f) : f);
    if (props.searchRange) {
        shapes.push({ type: 'rect', xref: 'x', yref: 'paper', x0: props.searchRange[0], x1: props.searchRange[1], y0: 0, y1: 1, fillcolor: 'rgba(242,101,34,0.05)', line: { width: 0 }, layer: 'below' });
    }
    if (o.showT10 && props.t10) {
        const fmin = props.frequency[0] ?? props.t10 / 10;
        shapes.push({ type: 'rect', xref: 'x', yref: 'paper', x0: Math.min(fmin, props.t10), x1: props.t10, y0: 0, y1: 1, fillcolor: 'rgba(120,125,140,0.12)', line: { width: 0 }, layer: 'below' });
        shapes.push({ type: 'line', xref: 'x', yref: 'paper', x0: props.t10, x1: props.t10, y0: 0, y1: 1, line: { color: '#6b7280', width: 1.2, dash: 'dash' } });
        annotations.push({ x: fx(props.t10), y: 0.98, xref: 'x', yref: 'paper', text: `T10 = ${fmtNum(props.t10, 3)} Hz`, showarrow: false, xanchor: 'left', font: { size: 10, color: '#6b7280' } });
    }
    if (props.selected) {
        shapes.push({ type: 'line', xref: 'x', yref: 'paper', x0: props.selected.frequency, x1: props.selected.frequency, y0: 0, y1: 1, line: { color: '#00b8d9', width: 1.5 } });
        annotations.push({ x: fx(props.selected.frequency), y: 0.02, xref: 'x', yref: 'paper', text: ` ${fmtNum(props.selected.frequency, 4)} Hz`, showarrow: false, xanchor: 'left', yanchor: 'bottom', font: { size: 11, color: '#0097b2' } });
        annotations.push({
            x: fx(props.selected.frequency), y: props.selected.amplitude, xref: 'x', yref: 'y', text: `f0 = ${fmtNum(props.selected.frequency, 4)} Hz, A = ${fmtNum(props.selected.amplitude, 3)}`,
            showarrow: true, arrowhead: 0, ax: 40, ay: -32, font: { size: 11, color: BRAND.orange }, bgcolor: app.isDark ? 'rgba(28,31,39,0.85)' : 'rgba(255,255,255,0.85)',
        });
    }
    const xaxis: Partial<Layout>['xaxis'] = { title: { text: 'Frequency (Hz)' }, type: o.freqLog ? 'log' : 'linear', exponentformat: 'power' };
    if (o.freqRange) xaxis.range = o.freqLog ? [Math.log10(o.freqRange[0]), Math.log10(o.freqRange[1])] : [o.freqRange[0], o.freqRange[1]];
    const yaxis: Partial<Layout>['yaxis'] = { title: { text: 'H/V spectral ratio (–)' }, rangemode: 'tozero' };
    if (o.ratioRange) yaxis.range = [o.ratioRange[0], o.ratioRange[1]];
    const hasDb = !!props.spectra && (o.dbHorizontal || o.dbVertical);
    const l: Partial<Layout> = {
        xaxis, yaxis, shapes, annotations,
        dragmode: o.selectWindows ? 'select' : 'zoom',
        legend: { orientation: 'h', x: 0, y: 1.0, yanchor: 'bottom', font: { size: 10.5 } },
        margin: { l: 56, r: hasDb ? 64 : 16, t: 72, b: 44 },
    };
    if (hasDb) {
        l.yaxis2 = { title: { text: 'Signal spectra (dB re 1 count)' }, overlaying: 'y', side: 'right', showgrid: false, ...(o.dbRange ? { range: [o.dbRange[0], o.dbRange[1]] } : {}) };
    }
    return l;
});

function onClick(ev: PlotMouseEvent) {
    const p = ev.points?.[0];
    if (p && typeof p.x === 'number') emit('pick', p.x);
}
function onSelected(ev: PlotSelectionEvent | undefined) {
    if (!opt.value.selectWindows || !ev?.points?.length) return;
    const idx = new Set<number>();
    for (const p of ev.points) {
        const w = traceWindow[p.curveNumber];
        if (w !== undefined) idx.add(w);
    }
    if (idx.size) emit('selectWindows', [...idx].sort((a, b) => a - b));
}
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" :title="title" :export-name="exportName" :extra-exports="extraExports" @click="onClick" @selected="onSelected" />
</template>
