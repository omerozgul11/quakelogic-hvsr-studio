<script setup lang="ts">
export interface SelectOption { value: string | number | null; label: string; disabled?: boolean }
interface Props { modelValue: string | number | null; options: SelectOption[]; disabled?: boolean; placeholder?: string }
const props = defineProps<Props>();
const emit = defineEmits<{ 'update:modelValue': [value: string | number | null] }>();

function onChange(e: Event) {
    const idx = Number((e.target as HTMLSelectElement).value);
    if (idx < 0) { emit('update:modelValue', null); return; }
    const opt = props.options[idx];
    emit('update:modelValue', opt ? opt.value : null);
}
function currentIndex(): number {
    return props.options.findIndex((o) => o.value === props.modelValue);
}
</script>

<template>
    <select class="input truncate" :value="currentIndex()" :disabled="disabled" @change="onChange">
        <option v-if="placeholder" :value="-1" disabled>{{ placeholder }}</option>
        <option v-for="(o, i) in options" :key="i" :value="i" :disabled="o.disabled">{{ o.label }}</option>
    </select>
</template>
