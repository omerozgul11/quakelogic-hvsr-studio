<script setup lang="ts">
export interface TabItem { key: string; label: string; disabled?: boolean; title?: string }
interface Props { modelValue: string; tabs: TabItem[]; small?: boolean }
defineProps<Props>();
const emit = defineEmits<{ 'update:modelValue': [key: string] }>();
</script>

<template>
    <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div class="segmented" :class="{ sm: small }" role="tablist">
            <button
                v-for="t in tabs"
                :key="t.key"
                role="tab"
                :aria-selected="t.key === modelValue"
                :disabled="t.disabled"
                :title="t.title ?? (t.disabled ? 'Not available for this result' : '')"
                class="seg-btn"
                :class="{ active: t.key === modelValue }"
                @click="emit('update:modelValue', t.key)"
            >
                {{ t.label }}
            </button>
        </div>
        <div v-if="$slots.end" class="ml-auto flex items-center gap-3"><slot name="end" /></div>
    </div>
</template>
