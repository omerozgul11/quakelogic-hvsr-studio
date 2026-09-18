<script setup lang="ts">
import { CircleHelp } from 'lucide-vue-next';
interface Props { label: string; help?: string; error?: string | null; inline?: boolean; for?: string; hint?: string }
defineProps<Props>();
</script>

<template>
    <label class="block min-w-0" :class="inline ? 'flex items-center justify-between gap-3' : ''">
        <span class="flex items-center gap-1 text-[12px] font-medium text-muted" :class="inline ? 'min-w-0 leading-tight' : 'mb-1.5'">
            <span class="truncate">{{ label }}</span>
            <CircleHelp v-if="hint" class="size-3.5 text-faint shrink-0 cursor-help" :title="hint" />
        </span>
        <span :class="inline ? 'w-44 shrink-0' : 'block'"><slot /></span>
        <span v-if="error" class="block text-[11.5px] mt-1 text-bad-500">{{ error }}</span>
        <span v-else-if="help && !inline" class="help block">{{ help }}</span>
    </label>
</template>
