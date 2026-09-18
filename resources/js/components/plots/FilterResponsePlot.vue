<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { BRAND } from '@/utils/plotTheme';
import type { FilterResponse } from '@/api/types';

interface Props { response: FilterResponse | null; height?: number }
const props = withDefaults(defineProps<Props>(), { height: 200 });

const data = computed<Data[]>(() => props.response ? [{
    x: props.response.frequency, y: props.response.magnitude_db, type: 'scatter', mode: 'lines', line: { color: BRAND.navy, width: 1.6 }, name: '|H(f)|',
    hovertemplate: 'f=%{x:.3g} Hz<br>%{y:.1f} dB<extra></extra>',
}] : []);
const layout = computed<Partial<Layout>>(() => ({
    margin: { l: 48, r: 8, t: 8, b: 36 },
    xaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power' },
    yaxis: { title: { text: 'Gain (dB)' }, range: [-80, 5] },
    showlegend: false,
    shapes: [{ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: -3, y1: -3, line: { color: BRAND.orange, width: 1, dash: 'dot' } }],
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" export-name="filter-response" hide-toolbar />
</template>
