<script setup lang="ts">
import { computed } from 'vue';

interface Props {
    modelValue: number | null;
    min?: number;
    max?: number;
    step?: number | 'any';
    unit?: string;
    placeholder?: string;
    disabled?: boolean;
    invalid?: boolean;
    nullable?: boolean;
}
const props = withDefaults(defineProps<Props>(), { step: 'any', nullable: false, disabled: false, invalid: false });
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>();

const text = computed(() => (props.modelValue === null || props.modelValue === undefined ? '' : String(props.modelValue)));

function onInput(e: Event) {
    const raw = (e.target as HTMLInputElement).value.trim();
    if (raw === '') {
        emit('update:modelValue', props.nullable ? null : props.modelValue);
        return;
    }
    const v = Number(raw.replace(',', '.'));
    if (Number.isFinite(v)) emit('update:modelValue', v);
}
</script>

<template>
    <span class="relative block">
        <input
            type="number"
            class="input num"
            :style="{ paddingRight: unit ? `${unit.length * 7 + 20}px` : undefined }"
            :class="{ 'is-invalid': invalid }"
            :value="text"
            :min="min"
            :max="max"
            :step="step"
            :placeholder="placeholder"
            :disabled="disabled"
            @input="onInput"
        />
        <span v-if="unit" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] text-faint pointer-events-none">{{ unit }}</span>
    </span>
</template>
