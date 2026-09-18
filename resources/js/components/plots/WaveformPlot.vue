<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Data, Layout, PlotRelayoutEvent, PlotMouseEvent, PlotSelectionEvent, Shape } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { componentColor } from '@/utils/plotTheme';
import { useAppStore } from '@/stores/app';
import type { ComponentKey, DisplayData } from '@/api/types';

interface Props {
    raw: DisplayData | null;
    processed?: DisplayData | null;
    showRaw?: boolean;
    showProcessed?: boolean;
    units?: string;
    shapes?: Partial<Shape>[];
    height?: number;
    title?: string;
    exportName?: string;
    channels?: Partial<Record<ComponentKey, string>>;
    loading?: boolean;
    /** 'select' enables box selection (free window selection); default zoom. */
    dragmode?: 'zoom' | 'select' | 'pan';
    /** Use one common amplitude scale for the three channels. */
    commonY?: boolean;
    annotations?: Partial<Layout>['annotations'];
}
const props = withDefaults(defineProps<Props>(), { showRaw: true, showProcessed: true, units: 'counts', height: 420, exportName: 'waveforms', loading: false, dragmode: 'zoom', commonY: false });
const emit = defineEmits<{ range: [range: [number, number] | null]; click: [ev: PlotMouseEvent]; selected: [range: [number, number] | null] }>();

const app = useAppStore();
const comps: ComponentKey[] = ['n', 'e', 'z'];
const chart = ref<InstanceType<typeof PlotlyChart> | null>(null);

const data = computed<Data[]>(() => {
    const out: Data[] = [];
    comps.forEach((c, i) => {
        const ax = i === 0 ? '' : String(i + 1);
        const label = props.channels?.[c] ?? c.toUpperCase();
        const r = props.raw?.components[c];
        const p = props.processed?.components[c];
        if (r && props.showRaw) {
            out.push({
                x: r.t, y: r.v, type: 'scattergl', mode: 'lines', name: `${label} raw`,
                line: { color: props.processed && props.showProcessed ? 'rgba(130,135,150,0.55)' : componentColor(c, app.isDark), width: 1 },
                xaxis: 'x', yaxis: `y${ax}`, hovertemplate: `t=%{x:.3f} s<br>${label}=%{y:.4g} ${props.units}<extra>raw</extra>`,
            });
        }
        if (p && props.showProcessed) {
            out.push({
                x: p.t, y: p.v, type: 'scattergl', mode: 'lines', name: `${label} processed`,
                line: { color: componentColor(c, app.isDark), width: 1 },
                xaxis: 'x', yaxis: `y${ax}`, hovertemplate: `t=%{x:.3f} s<br>${label}=%{y:.4g} ${props.units}<extra>processed</extra>`,
            });
        }
    });
    return out;
});

const commonRange = computed<[number, number] | null>(() => {
    if (!props.commonY) return null;
    let m = 0;
    for (const src of [props.raw, props.processed]) {
        if (!src) continue;
        for (const c of comps) { const v = src.components[c]?.v; if (v) for (const x of v) if (Number.isFinite(x) && Math.abs(x) > m) m = Math.abs(x); }
    }
    return m > 0 ? [-m * 1.05, m * 1.05] : null;
});

const layout = computed<Partial<Layout>>(() => {
    const r = commonRange.value;
    const yr = r ? { range: r, autorange: false as const } : {};
    return {
        height: props.height,
        margin: { l: 64, r: 16, t: props.title ? 64 : 40, b: 40 },
        grid: { rows: 3, columns: 1, pattern: 'coupled', roworder: 'top to bottom' },
        dragmode: props.dragmode,
        selectdirection: 'h',
        xaxis: { title: { text: 'Time (s) from record start' }, showspikes: true, spikemode: 'across', spikethickness: 1 },
        yaxis: { title: { text: `${props.channels?.n ?? 'N'} (${props.units})` }, domain: [0.7, 1], ...yr },
        yaxis2: { title: { text: `${props.channels?.e ?? 'E'} (${props.units})` }, domain: [0.36, 0.66], ...yr },
        yaxis3: { title: { text: `${props.channels?.z ?? 'Z'} (${props.units})` }, domain: [0.02, 0.32], ...yr },
        shapes: props.shapes ?? [],
        annotations: props.annotations ?? [],
        showlegend: true,
        legend: { orientation: 'h', x: 0, xanchor: 'left', y: 1.0, yanchor: 'bottom', font: { size: 10 } },
    };
});

function onSelected(ev: PlotSelectionEvent | undefined) {
    const range = (ev as { range?: { x?: number[] } } | undefined)?.range?.x;
    if (range && range.length === 2 && Number.isFinite(range[0]) && Number.isFinite(range[1])) emit('selected', [Math.min(range[0], range[1]), Math.max(range[0], range[1])]);
    else emit('selected', null);
}

function onRelayout(e: PlotRelayoutEvent) {
    const ev = e as Record<string, unknown>;
    if (ev['xaxis.autorange']) { emit('range', null); return; }
    const a = ev['xaxis.range[0]'];
    const b = ev['xaxis.range[1]'];
    if (typeof a === 'number' && typeof b === 'number') emit('range', [a, b]);
    else if (Array.isArray(ev['xaxis.range'])) {
        const r = ev['xaxis.range'] as number[];
        emit('range', [r[0], r[1]]);
    }
}
defineExpose({ chart });
</script>

<template>
    <PlotlyChart ref="chart" :data="data" :layout="layout" :height="height" :title="title" :export-name="exportName" :loading="loading" @relayout="onRelayout" @click="emit('click', $event)" @selected="onSelected" />
</template>
