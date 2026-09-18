<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import type { CompareEntry } from '@/api/types';

interface Props { entries: CompareEntry[]; showBands?: boolean; height?: number }
const props = withDefaults(defineProps<Props>(), { showBands: false, height: 440 });

const palette = ['#2f3238', '#F26522', '#2f8f5b', '#2f6fb0', '#8b5cf6', '#c58a12', '#c9463d', '#0f766e', '#7c3aed', '#b45309'];

const data = computed<Data[]>(() => {
    const out: Data[] = [];
    props.entries.forEach((e, i) => {
        const color = palette[i % palette.length];
        const name = e.name + (e.recording_name ? ` · ${e.recording_name}` : '');
        if (props.showBands) {
            out.push({ x: e.frequency, y: e.upper, type: 'scatter', mode: 'lines', line: { width: 0, color: 'rgba(0,0,0,0)' }, showlegend: false, hoverinfo: 'skip' });
            out.push({ x: e.frequency, y: e.lower, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: color + '22', line: { width: 0, color: 'rgba(0,0,0,0)' }, showlegend: false, hoverinfo: 'skip' });
        }
        out.push({ x: e.frequency, y: e.curve, type: 'scatter', mode: 'lines', name, line: { color, width: 1.8 }, hovertemplate: 'f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra>' + name + '</extra>' });
        if (e.peak) {
            out.push({ x: [e.peak.frequency], y: [e.peak.amplitude], type: 'scatter', mode: 'markers', marker: { color, size: 10, symbol: 'diamond', line: { color: '#fff', width: 1 } }, showlegend: false, hovertemplate: 'f0=%{x:.3g} Hz<br>A0=%{y:.3f}<extra>' + name + '</extra>' });
        }
    });
    return out;
});
const layout = computed<Partial<Layout>>(() => ({
    xaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power' },
    yaxis: { title: { text: 'H/V spectral ratio (–)' }, rangemode: 'tozero' },
    legend: { orientation: 'h', x: 0, xanchor: 'left', y: 1.0, yanchor: 'bottom', font: { size: 10.5 } },
    margin: { l: 56, r: 16, t: 64 + 16 * Math.max(0, props.entries.length - 2), b: 44 },
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="Comparison of selected mean H/V curves (diamonds: selected peaks)" export-name="comparison" />
</template>
