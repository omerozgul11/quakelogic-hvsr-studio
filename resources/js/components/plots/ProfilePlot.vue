<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import type { ModelLayer } from '@/api/types';

/** Ground profile: Vs (blue, bottom axis) and Vp (red, top axis) versus depth (downwards), step plot. */
interface Props { layers: ModelLayer[]; showVp?: boolean; depthMax?: number | null; marker?: number | null; height?: number }
const props = withDefaults(defineProps<Props>(), { showVp: true, depthMax: null, marker: null, height: 460 });

const steps = computed(() => {
    const zs: number[] = [];
    const vs: number[] = [];
    const vp: number[] = [];
    let z = 0;
    const layers = props.layers;
    const totalKnown = layers.reduce((a, l) => a + (l.thickness_m ?? 0), 0);
    const bottom = props.depthMax ?? Math.max(10, totalKnown * 1.15 + 5);
    layers.forEach((l, i) => {
        const h = l.thickness_m ?? Math.max(bottom - z, 1);
        const z1 = i === layers.length - 1 ? Math.max(bottom, z + 1) : z + h;
        zs.push(z, z1); vs.push(l.vs, l.vs); vp.push(l.vp ?? NaN, l.vp ?? NaN);
        z = z1;
    });
    return { zs, vs, vp, bottom: z };
});
const data = computed<Data[]>(() => {
    const out: Data[] = [{ x: steps.value.vs, y: steps.value.zs, type: 'scatter', mode: 'lines', line: { color: '#1d4ed8', width: 2.5 }, name: 'Vs', hovertemplate: 'Vs=%{x:.0f} m/s<br>depth=%{y:.1f} m<extra></extra>' }];
    if (props.showVp) out.push({ x: steps.value.vp, y: steps.value.zs, type: 'scatter', mode: 'lines', xaxis: 'x2', line: { color: '#dc2626', width: 2.5 }, name: 'Vp', hovertemplate: 'Vp=%{x:.0f} m/s<br>depth=%{y:.1f} m<extra></extra>' });
    return out;
});
const layout = computed<Partial<Layout>>(() => ({
    xaxis: { title: { text: 'Vs (m/s)' }, side: 'bottom', rangemode: 'tozero', color: '#1d4ed8' },
    xaxis2: { title: { text: 'Vp (m/s)' }, side: 'top', overlaying: 'x', rangemode: 'tozero', color: '#dc2626', showgrid: false },
    yaxis: { title: { text: 'Depth (m)' }, autorange: 'reversed', rangemode: 'tozero' },
    shapes: props.marker !== null ? [{ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: props.marker, y1: props.marker, line: { color: '#F26522', width: 1, dash: 'dot' } }] : [],
    legend: { orientation: 'h', x: 0, y: -0.14, yanchor: 'top', font: { size: 10.5 } },
    margin: { l: 56, r: 16, t: 84, b: 60 },
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="Ground profile" export-name="ground-profile" />
</template>
