<script setup lang="ts">
import type { Component } from 'vue';
interface Props { title: string; description?: string; icon?: Component; compact?: boolean }
defineProps<Props>();
</script>

<template>
    <div class="flex flex-col items-center justify-center text-center px-6" :class="compact ? 'py-6' : 'py-14'">
        <div v-if="icon" class="mb-3 rounded-2xl p-3.5 bg-surface-2 text-faint"><component :is="icon" class="size-6" /></div>
        <h3 class="text-[14px] font-semibold">{{ title }}</h3>
        <p v-if="description" class="text-[12.5px] text-muted mt-1 max-w-md">{{ description }}</p>
        <div v-if="$slots.default" class="mt-4 flex flex-wrap justify-center gap-2"><slot /></div>
    </div>
</template>
