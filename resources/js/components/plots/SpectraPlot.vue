<script setup lang="ts">
import { computed } from 'vue';
import type { Data, Layout } from 'plotly.js';
import PlotlyChart from './PlotlyChart.vue';
import { componentColor } from '@/utils/plotTheme';
import { useAppStore } from '@/stores/app';
import type { ComponentKey } from '@/api/types';

interface Props {
    frequency: number[];
    series: Partial<Record<ComponentKey | 'h', (number | null)[] | undefined>>;
    kind: 'fas' | 'psd';
    units?: string;
    height?: number;
    title?: string;
    channels?: Partial<Record<ComponentKey, string>>;
    exportName?: string;
    extraExports?: { label: string; action: () => void | Promise<void> }[];
}
const props = withDefaults(defineProps<Props>(), { height: 320, exportName: 'spectra' });
const app = useAppStore();

const data = computed<Data[]>(() =>
    (Object.keys(props.series) as (ComponentKey | 'h')[])
        .filter((k) => props.series[k])
        .map((k) => ({
            x: props.frequency,
            y: props.series[k] as (number | null)[],
            type: 'scatter',
            mode: 'lines',
            name: k === 'h' ? 'H (combined)' : (props.channels?.[k] ?? k.toUpperCase()),
            line: { color: componentColor(k, app.isDark), width: k === 'h' ? 2 : 1.4, dash: k === 'h' ? 'dot' : 'solid' },
            hovertemplate: 'f=%{x:.3g} Hz<br>%{y:.4g} ' + (props.units ?? (props.kind === 'psd' ? 'counts²/Hz' : 'counts·s')) + '<extra>' + (k === 'h' ? 'H' : k.toUpperCase()) + '</extra>',
        })),
);

const layout = computed<Partial<Layout>>(() => ({
    xaxis: { title: { text: 'Frequency (Hz)' }, type: 'log', exponentformat: 'power' },
    yaxis: {
        title: { text: props.kind === 'psd' ? `PSD (${props.units ?? 'counts²/Hz'})` : `Fourier amplitude (${props.units ?? 'counts·s'})` },
        type: 'log', exponentformat: 'power',
    },
}));
</script>

<template>
    <PlotlyChart :data="data" :layout="layout" :height="height" :title="title" :export-name="exportName" :extra-exports="extraExports" />
</template>
