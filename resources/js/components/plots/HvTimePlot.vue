<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout, Shape } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { JET, windowColor } from '@/utils/windowPalette';

/** H/V versus time (GeoExplorer "H/V time graph"): one column per window, log frequency on y, jet colours. */
interface Props {
    timesS: number[];
    frequency: number[];
    matrix: (number | null)[][];
    startTime?: string | null;
    accepted?: boolean[];
    /** Colour scale maximum as a percentage of the matrix maximum, or a manual maximum. */
    maxPercent?: number;
    manualMax?: number | null;
    height?: number;
    extraExports?: { label: string; action: () => void | Promise<void> }[];
}
const props = withDefaults(defineProps<Props>(), { maxPercent: 100, manualMax: null, height: 440 });

const t0 = computed(() => { const d = props.startTime ? new Date(props.startTime) : null; return d && !Number.isNaN(d.getTime()) ? d.getTime() : null; });
const useClock = computed(() => t0.value !== null);
const xs = computed(() => props.timesS.map((s) => (useClock.value ? new Date(t0.value! + s * 1000).toISOString() : s)));
const zmax = computed(() => {
    if (props.manualMax) return props.manualMax;
    let m = 0;
    for (const row of props.matrix) for (const v of row) if (v !== null && Number.isFinite(v) && v > m) m = v;
    return Math.max(1e-6, (m * props.maxPercent) / 100);
});
/** Transpose windows × frequency → frequency × windows for the heatmap. */
const z = computed(() => props.frequency.map((_, fi) => props.matrix.map((row) => (row[fi] === undefined ? null : row[fi]))));
const data = computed<Data[]>(() => [{
    x: xs.value, y: props.frequency, z: z.value, type: 'heatmap', colorscale: JET, zmin: 0, zmax: zmax.value, zsmooth: 'best',
    colorbar: { title: { text: 'H/V level', side: 'right' }, thickness: 12, len: 0.9 },
    hovertemplate: (useClock.value ? '%{x|%H:%M:%S}' : 't=%{x:.1f} s') + '<br>f=%{y:.3g} Hz<br>H/V=%{z:.2f}<extra></extra>',
}]);
const shapes = computed<Partial<Shape>[]>(() => {
    const n = props.timesS.length;
    if (!n) return [];
    const out: Partial<Shape>[] = [];
    props.timesS.forEach((s, i) => {
        if (props.accepted && !props.accepted[i]) return;
        const next = props.timesS[i + 1] ?? s + (props.timesS[i] - (props.timesS[i - 1] ?? s - 30));
        const x0 = useClock.value ? new Date(t0.value! + s * 1000).toISOString() : s;
        const x1 = useClock.value ? new Date(t0.value! + next * 1000).toISOString() : next;
        out.push({ type: 'rect', xref: 'x', yref: 'paper', x0, x1, y0: 1.01, y1: 1.05, fillcolor: windowColor(i, n), line: { width: 0 } });
    });
    return out;
});
const layout = computed<Partial<Layout>>(() => ({
    xaxis: { title: { text: useClock.value ? 'Time (UTC)' : 'Time (s) from record start' }, type: useClock.value ? 'date' : 'linear', tickformat: useClock.value ? '%H:%M:%S' : undefined },
    yaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power' },
    shapes: shapes.value, showlegend: false, margin: { l: 56, r: 16, t: 84, b: 44 },
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="H/V versus time — one column per accepted window (colour strip: window colours)" export-name="hv-time" :extra-exports="extraExports" />
</template>
