<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';

interface Props { t: number[]; f: number[]; db: (number | null)[][]; label: string; height?: number; logFreq?: boolean; units?: string }
const props = withDefaults(defineProps<Props>(), { height: 240, logFreq: true });

const data = computed<Data[]>(() => [{
    x: props.t, y: props.f, z: props.db, type: 'heatmap', colorscale: 'Viridis',
    colorbar: { title: { text: `PSD (${props.units ?? 'dB re counts²/Hz'})`, side: 'right' }, thickness: 10, len: 0.9 },
    hovertemplate: 't=%{x:.1f} s<br>f=%{y:.3g} Hz<br>PSD=%{z:.1f} dB<extra>' + props.label + '</extra>',
}]);
const layout = computed<Partial<Layout>>(() => ({
    margin: { l: 56, r: 16, t: 26, b: 40 },
    xaxis: { title: { text: 'Time (s)' } },
    yaxis: { title: { text: 'Frequency (Hz)' }, type: props.logFreq ? 'log' : 'linear' },
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" :title="`${label} — spectrogram (10·log10 PSD, counts²/Hz)`" :export-name="`spectrogram-${label}`" />
</template>
