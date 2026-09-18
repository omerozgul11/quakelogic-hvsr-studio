<script setup lang="ts">
import { computed } from 'vue';
interface Props { tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'brand' | 'accent'; label?: string }
const props = withDefaults(defineProps<Props>(), { tone: 'neutral' });
const cls = computed(() => ({
    neutral: 'bg-black/6 text-muted dark:bg-white/10',
    ok: 'bg-ok-500/12 text-ok-500',
    warn: 'bg-warn-500/15 text-warn-500',
    bad: 'bg-bad-500/12 text-bad-500',
    brand: 'bg-brand-500/12 text-brand-700 dark:text-brand-300',
    accent: 'bg-accent-500/12 text-accent-600 dark:text-accent-300',
}[props.tone]));
</script>

<template>
    <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap" :class="cls"><slot>{{ label }}</slot></span>
</template>
