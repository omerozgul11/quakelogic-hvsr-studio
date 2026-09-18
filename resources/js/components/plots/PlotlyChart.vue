<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch, computed } from 'vue';
import Plotly from 'plotly.js-cartesian-dist-min';
import type { Data, Layout, Config, PlotRelayoutEvent, PlotMouseEvent, PlotSelectionEvent } from 'plotly.js';
import { Download, Maximize2 } from 'lucide-vue-next';
import { useAppStore } from '@/stores/app';
import { baseLayout, baseConfig } from '@/utils/plotTheme';
import Dropdown from '@/components/ui/Dropdown.vue';
import MenuItem from '@/components/ui/MenuItem.vue';

interface Props {
    data: Data[];
    layout?: Partial<Layout>;
    config?: Partial<Config>;
    height?: number | string;
    title?: string;
    /** File name (without extension) used for image exports. */
    exportName?: string;
    /** Extra export entries (e.g. PDF via API) rendered in the export menu. */
    extraExports?: { label: string; action: () => void | Promise<void> }[];
    loading?: boolean;
    hideToolbar?: boolean;
}
const props = withDefaults(defineProps<Props>(), { height: 320, exportName: 'plot', loading: false, hideToolbar: false });
const emit = defineEmits<{ relayout: [ev: PlotRelayoutEvent]; click: [ev: PlotMouseEvent]; doubleclick: []; selected: [ev: PlotSelectionEvent | undefined] }>();

const app = useAppStore();
const el = ref<HTMLDivElement | null>(null);
let ro: ResizeObserver | null = null;
let drawn = false;

const heightStyle = computed(() => (typeof props.height === 'number' ? `${props.height}px` : props.height));

function mergedLayout(): Partial<Layout> {
    const base = baseLayout(app.isDark);
    const l = props.layout ?? {};
    return {
        ...base,
        ...l,
        xaxis: { ...base.xaxis, ...(l.xaxis ?? {}) },
        yaxis: { ...base.yaxis, ...(l.yaxis ?? {}) },
        ...(l.yaxis2 ? { yaxis2: { ...base.yaxis, ...l.yaxis2 } } : {}),
        ...(l.yaxis3 ? { yaxis3: { ...base.yaxis, ...l.yaxis3 } } : {}),
        ...(l.xaxis2 ? { xaxis2: { ...base.xaxis, ...l.xaxis2 } } : {}),
        ...(l.xaxis3 ? { xaxis3: { ...base.xaxis, ...l.xaxis3 } } : {}),
        title: props.title ? { text: props.title, font: { size: 13 }, x: 0, xanchor: 'left', y: 1, yanchor: 'top', pad: { t: 8 } } : l.title,
    };
}

async function draw() {
    if (!el.value) return;
    const node = el.value;
    await Plotly.react(node, props.data, mergedLayout(), { ...baseConfig, ...(props.config ?? {}) });
    if (!drawn) {
        drawn = true;
        const anyNode = node as unknown as { on: (ev: string, cb: (e: never) => void) => void };
        anyNode.on('plotly_relayout', (e: never) => emit('relayout', e as PlotRelayoutEvent));
        anyNode.on('plotly_click', (e: never) => emit('click', e as PlotMouseEvent));
        anyNode.on('plotly_doubleclick', () => emit('doubleclick'));
        anyNode.on('plotly_selected', (e: never) => emit('selected', e as PlotSelectionEvent | undefined));
    }
}

async function downloadImage(format: 'png' | 'svg') {
    if (!el.value) return;
    await Plotly.downloadImage(el.value, { format, filename: props.exportName, width: Math.max(1600, el.value.clientWidth * 2), height: Math.max(900, el.value.clientHeight * 2) });
}
function resetZoom() {
    if (el.value) void Plotly.relayout(el.value, { 'xaxis.autorange': true, 'yaxis.autorange': true });
}
defineExpose({ downloadImage, resetZoom, element: el });

onMounted(() => {
    void draw();
    ro = new ResizeObserver(() => { if (el.value) Plotly.Plots.resize(el.value); });
    if (el.value) ro.observe(el.value);
});
onBeforeUnmount(() => {
    ro?.disconnect();
    if (el.value) Plotly.purge(el.value);
});
watch(() => [props.data, props.layout, app.isDark], () => void draw(), { deep: true });
</script>

<template>
    <div class="relative min-w-0">
        <div v-if="!hideToolbar" class="absolute right-1 top-1 z-10 flex items-center gap-1">
            <button class="rounded p-1 text-faint hover:text-ui bg-surface/80" title="Reset zoom" @click="resetZoom"><Maximize2 class="size-3.5" /></button>
            <Dropdown label="Export" size="sm">
                <template #icon><Download class="size-3.5 text-faint" /></template>
                <MenuItem @click="downloadImage('png')">PNG (2×)</MenuItem>
                <MenuItem @click="downloadImage('svg')">SVG</MenuItem>
                <MenuItem v-for="x in extraExports ?? []" :key="x.label" @click="x.action()">{{ x.label }}</MenuItem>
            </Dropdown>
        </div>
        <div ref="el" class="w-full" :style="{ height: heightStyle }" />
        <div v-if="loading" class="absolute inset-0 grid place-items-center bg-surface/60 text-[12px] text-muted">Loading…</div>
    </div>
</template>
