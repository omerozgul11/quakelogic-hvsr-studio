<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { BRAND } from '@/utils/plotTheme';
import { JET } from '@/utils/windowPalette';

interface Props {
    azimuths: number[]; frequency: number[]; matrix: (number | null)[][]; peakFrequency?: (number | null)[];
    maxPercent?: number; manualMax?: number | null; showPeaks?: boolean;
    height?: number; extraExports?: { label: string; action: () => void | Promise<void> }[];
}
const props = withDefaults(defineProps<Props>(), { height: 360, maxPercent: 100, manualMax: null, showPeaks: true });

const zmax = computed(() => {
    if (props.manualMax) return props.manualMax;
    let m = 0;
    for (const row of props.matrix) for (const v of row) if (v !== null && Number.isFinite(v) && v > m) m = v;
    return Math.max(1e-6, (m * props.maxPercent) / 100);
});
/** matrix is azimuth × frequency; draw frequency on y (log) and azimuth on x like QLExplorer. */
const z = computed(() => props.frequency.map((_, fi) => props.matrix.map((row) => row[fi] ?? null)));
const data = computed<Data[]>(() => {
    const out: Data[] = [{
        x: props.azimuths, y: props.frequency, z: z.value, type: 'heatmap', colorscale: JET, zmin: 0, zmax: zmax.value, zsmooth: 'best',
        colorbar: { title: { text: 'H/V level', side: 'right' }, thickness: 12, len: 0.9 },
        hovertemplate: 'az=%{x}°<br>f=%{y:.3g} Hz<br>H/V=%{z:.2f}<extra></extra>',
    }];
    if (props.peakFrequency && props.showPeaks) {
        out.push({ x: props.azimuths, y: props.peakFrequency, type: 'scatter', mode: 'markers', marker: { color: BRAND.orange, size: 6, symbol: 'diamond', line: { color: '#fff', width: 0.5 } }, name: 'peak per azimuth', hovertemplate: 'az=%{x}°<br>f0=%{y:.3g} Hz<extra></extra>' });
    }
    return out;
});
const layout = computed<Partial<Layout>>(() => ({
    xaxis: { title: { text: 'Azimuth (° clockwise from N)' }, dtick: 45, range: [0, 180] },
    yaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power' },
    showlegend: false,
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="H/V rotate graph — single rotated horizontal Hθ = N cos θ + E sin θ over Z" export-name="azimuthal" :extra-exports="extraExports" />
</template>
