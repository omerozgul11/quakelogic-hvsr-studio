<script setup lang="ts">
import { computed } from 'vue';
import type { Layout, PlotMouseEvent, Shape } from 'plotly.js';
import WaveformPlot from './WaveformPlot.vue';
import { windowColorFor } from '@/utils/windowPalette';
import type { DisplayData, WindowItem, ComponentKey } from '@/api/types';

interface Props {
    data: DisplayData | null;
    windows: WindowItem[];
    units?: string;
    channels?: Partial<Record<ComponentKey, string>>;
    height?: number;
    loading?: boolean;
    /** Hide the overlays of accepted windows to inspect the signal (GeoExplorer "Hide selected windows"). */
    hideSelected?: boolean;
    /** Drag a box to draw a new window instead of zooming. */
    freeSelect?: boolean;
    commonY?: boolean;
    bookmarks?: number[];
    cursor?: number | null;
    title?: string;
}
const props = withDefaults(defineProps<Props>(), { height: 400, loading: false, hideSelected: false, freeSelect: false, commonY: false, title: 'Windows — coloured: accepted (rainbow by time), grey: rejected · click a window to toggle it' });
const emit = defineEmits<{ toggle: [index: number]; range: [range: [number, number] | null]; draw: [range: [number, number]] }>();

const shapes = computed<Partial<Shape>[]>(() => {
    const n = props.windows.length;
    const out: Partial<Shape>[] = [];
    for (const w of props.windows) {
        if (w.accepted && props.hideSelected) continue;
        out.push({
            type: 'rect', xref: 'x', yref: 'paper', x0: w.start_s, x1: w.end_s, y0: 0, y1: 1,
            fillcolor: w.accepted ? windowColorFor(w, n, 0.3) : 'rgba(120,125,140,0.14)',
            line: { width: 1, color: w.accepted ? windowColorFor(w, n, 0.9) : 'rgba(120,125,140,0.45)' }, layer: 'below',
        });
    }
    for (const b of props.bookmarks ?? []) {
        out.push({ type: 'line', xref: 'x', yref: 'paper', x0: b, x1: b, y0: 0, y1: 1, line: { color: '#00d5ff', width: 1.5, dash: 'dot' } });
    }
    if (props.cursor !== null && props.cursor !== undefined) {
        out.push({ type: 'line', xref: 'x', yref: 'paper', x0: props.cursor, x1: props.cursor, y0: 0, y1: 1, line: { color: '#F26522', width: 2 } });
    }
    return out;
});
const annotations = computed<Partial<Layout>['annotations']>(() =>
    (props.bookmarks ?? []).map((b, i) => ({ x: b, y: 1, xref: 'x', yref: 'paper', text: `B${i + 1}`, showarrow: false, yanchor: 'bottom', font: { size: 9, color: '#0097b2' } })),
);

function onClick(ev: PlotMouseEvent) {
    if (props.freeSelect) return;
    const p = ev.points?.[0];
    if (!p || typeof p.x !== 'number') return;
    const t = p.x;
    let best = -1;
    let bestD = Infinity;
    for (const w of props.windows) {
        if (t >= w.start_s && t <= w.end_s) {
            const d = Math.abs((w.start_s + w.end_s) / 2 - t);
            if (d < bestD) { bestD = d; best = w.index; }
        }
    }
    if (best >= 0) emit('toggle', best);
}
function onSelected(r: [number, number] | null) {
    if (r && props.freeSelect && r[1] - r[0] > 0.5) emit('draw', r);
}
</script>

<template>
    <WaveformPlot :raw="data" :shapes="shapes" :annotations="annotations" :units="units" :channels="channels" :height="height" :loading="loading" :dragmode="freeSelect ? 'select' : 'zoom'" :common-y="commonY" export-name="windows" :title="freeSelect ? 'Free selection — drag a box across the trace to add a window' : title" @click="onClick" @range="emit('range', $event)" @selected="onSelected" />
</template>
