<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { BRAND } from '@/utils/plotTheme';
import type { HvsrResult } from '@/api/types';

interface Props { variability: HvsrResult['peak_variability']; selected?: number | null; height?: number; extraExports?: { label: string; action: () => void | Promise<void> }[] }
const props = withDefaults(defineProps<Props>(), { height: 280 });

const f0s = computed(() => props.variability.window_f0.filter((v): v is number => typeof v === 'number' && Number.isFinite(v)));

const data = computed<Data[]>(() => [{
    x: f0s.value, type: 'histogram', name: 'window f0', marker: { color: 'rgba(38,34,97,0.55)' }, nbinsx: 24,
    hovertemplate: 'f0 ∈ %{x} Hz<br>%{y} windows<extra></extra>',
}]);

const layout = computed<Partial<Layout>>(() => {
    const v = props.variability;
    const shapes: Partial<Layout>['shapes'] = [];
    const line = (x: number | null | undefined, color: string, dash: 'solid' | 'dot' | 'dash') => {
        if (typeof x === 'number') shapes.push({ type: 'line', xref: 'x', yref: 'paper', x0: x, x1: x, y0: 0, y1: 1, line: { color, width: 1.5, dash } });
    };
    line(v.median, BRAND.navy, 'solid');
    line(v.p16, 'rgba(38,34,97,0.6)', 'dot');
    line(v.p84, 'rgba(38,34,97,0.6)', 'dot');
    if (v.bootstrap && typeof v.bootstrap.f0_p2_5 === 'number' && typeof v.bootstrap.f0_p97_5 === 'number') {
        shapes.push({ type: 'rect', xref: 'x', yref: 'paper', x0: v.bootstrap.f0_p2_5, x1: v.bootstrap.f0_p97_5, y0: 0, y1: 1, fillcolor: 'rgba(242,101,34,0.10)', line: { width: 0 }, layer: 'below' });
    }
    line(props.selected ?? null, BRAND.orange, 'dash');
    return {
        xaxis: { title: { text: 'Window peak frequency f0 (Hz)' } },
        yaxis: { title: { text: 'Number of windows' } },
        shapes,
        showlegend: false,
        margin: { l: 56, r: 16, t: 28, b: 44 },
    };
});
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" title="Window-level peak distribution (median solid, 16–84 % dotted, bootstrap interval shaded, selected f0 dashed)" export-name="peak-distribution" :extra-exports="extraExports" />
</template>
