<script setup lang="ts">
interface Props { disabled?: boolean; danger?: boolean }
defineProps<Props>();
</script>

<template>
    <button type="button" class="w-[calc(100%-8px)] mx-1 text-left px-2.5 h-8 rounded-lg text-[12.5px] hover:bg-brand-500/10 hover:text-brand-700 dark:hover:text-brand-300 disabled:opacity-40 flex items-center gap-2 transition" :class="danger ? 'text-bad-500 hover:bg-bad-500/10 hover:text-bad-500' : ''" :disabled="disabled">
        <slot />
    </button>
</template>
