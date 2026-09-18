<script setup lang="ts">
import { computed } from 'vue';
interface Props { status: string | null | undefined; title?: string }
const props = defineProps<Props>();
const cls = computed(() => {
    switch (props.status) {
        case 'done': case 'ready': case 'ok': return 'bg-ok-500';
        case 'running': case 'queued': return 'bg-brand-400 animate-pulse';
        case 'failed': case 'invalid': case 'error': return 'bg-bad-500';
        case 'cancelled': case 'skipped': return 'bg-slate-400';
        case 'pending': return 'bg-warn-500';
        default: return 'bg-slate-300 dark:bg-slate-600';
    }
});
</script>

<template>
    <span class="inline-block size-2 rounded-full shrink-0" :class="cls" :title="title ?? (status ?? '')" />
</template>
