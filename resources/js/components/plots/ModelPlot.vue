<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import type { CurveSet } from '@/api/types';

/** Experimental H/V (mean + dashed σ curves) versus the synthetic curve of a ground model (GeoExplorer modelling view). */
interface Props {
    frequency: number[];
    curve: CurveSet | null;
    model: { frequency: number[]; hvsr: (number | null)[] } | null;
    showExperimental?: boolean;
    showStd?: boolean;
    showSynthetic?: boolean;
    link?: 'none' | 'experimental' | 'synthetic' | 'common';
    freqRange?: [number, number] | null;
    ratioRange?: [number, number] | null;
    height?: number;
}
const props = withDefaults(defineProps<Props>(), { showExperimental: true, showStd: true, showSynthetic: true, link: 'none', freqRange: null, ratioRange: null, height: 420 });

const EXP = '#d9a400';
const SYN = '#16a34a';
const data = computed<Data[]>(() => {
    const out: Data[] = [];
    if (props.curve && props.showExperimental) {
        if (props.showStd) {
            out.push({ x: props.frequency, y: props.curve.upper, type: 'scatter', mode: 'lines', line: { color: EXP, width: 1, dash: 'dash' }, name: '+σ', hovertemplate: 'f=%{x:.3g} Hz<br>+σ=%{y:.3f}<extra></extra>' });
            out.push({ x: props.frequency, y: props.curve.lower, type: 'scatter', mode: 'lines', line: { color: EXP, width: 1, dash: 'dash' }, name: '−σ', hovertemplate: 'f=%{x:.3g} Hz<br>−σ=%{y:.3f}<extra></extra>' });
        }
        out.push({ x: props.frequency, y: props.curve.values, type: 'scatter', mode: 'lines', line: { color: EXP, width: 2.4 }, name: 'Experimental H/V', hovertemplate: 'f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra>experimental</extra>' });
    }
    if (props.model && props.showSynthetic) {
        out.push({ x: props.model.frequency, y: props.model.hvsr, type: 'scatter', mode: 'lines', line: { color: SYN, width: 2.4 }, name: 'Synthetic H/V (model)', hovertemplate: 'f=%{x:.3g} Hz<br>H/V=%{y:.3f}<extra>synthetic</extra>' });
    }
    return out;
});
const layout = computed<Partial<Layout>>(() => {
    let range: [number, number] | null = props.freqRange;
    if (!range) {
        const ef = props.frequency;
        const mf = props.model?.frequency ?? [];
        const r = (a: number[]): [number, number] | null => (a.length ? [Math.min(...a), Math.max(...a)] : null);
        if (props.link === 'experimental') range = r(ef);
        else if (props.link === 'synthetic') range = r(mf);
        else if (props.link === 'common') { const a = r(ef); const b = r(mf); if (a && b) range = [Math.max(a[0], b[0]), Math.min(a[1], b[1])]; }
    }
    return {
        xaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power', ...(range ? { range: [Math.log10(range[0]), Math.log10(range[1])] } : {}) },
        yaxis: { title: { text: 'H/V ratio level (–)' }, rangemode: 'tozero', ...(props.ratioRange ? { range: props.ratioRange } : {}) },
        shapes: [{ type: 'line', xref: 'paper', yref: 'y', x0: 0, x1: 1, y0: 1, y1: 1, line: { color: '#9aa0ab', width: 1 } }],
        legend: { orientation: 'h', x: 0, y: 1.0, yanchor: 'bottom', font: { size: 10.5 } },
    };
});
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="H/V modelling — experimental (yellow) vs synthetic (green)" export-name="hv-model" />
</template>
