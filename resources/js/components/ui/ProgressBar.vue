<script setup lang="ts">
interface Props { value: number; indeterminate?: boolean; tone?: 'brand' | 'accent' | 'ok' | 'bad' }
withDefaults(defineProps<Props>(), { indeterminate: false, tone: 'brand' });
</script>

<template>
    <div class="h-1.5 w-full rounded-full bg-surface-2 overflow-hidden" role="progressbar" :aria-valuenow="Math.round(value * 100)">
        <div
            class="h-full rounded-full transition-[width] duration-300"
            :class="[
                tone === 'accent' ? 'bg-accent-500' : tone === 'ok' ? 'bg-ok-500' : tone === 'bad' ? 'bg-bad-500' : 'bg-brand-500 dark:bg-brand-300',
                indeterminate ? 'animate-pulse' : '',
            ]"
            :style="{ width: indeterminate ? '100%' : `${Math.max(2, Math.min(100, value * 100))}%` }"
        />
    </div>
</template>
