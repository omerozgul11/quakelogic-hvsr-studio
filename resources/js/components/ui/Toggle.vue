<script setup lang="ts">
interface Props { modelValue: boolean; label?: string; disabled?: boolean; small?: boolean; help?: string }
defineProps<Props>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();
</script>

<template>
    <label class="flex w-fit max-w-full items-center gap-2.5 cursor-pointer select-none" :class="{ 'opacity-50 cursor-not-allowed': disabled }" :title="help">
        <button
            type="button"
            role="switch"
            :aria-checked="modelValue"
            :disabled="disabled"
            class="relative shrink-0 rounded-full transition-colors duration-200"
            :class="[small ? 'h-[18px] w-[30px]' : 'h-[22px] w-[38px]', modelValue ? 'bg-brand-500' : 'bg-black/15 dark:bg-white/20']"
            @click="emit('update:modelValue', !modelValue)"
        >
            <span
                class="absolute top-[2px] left-[2px] rounded-full bg-white shadow-[0_1px_2px_rgba(0,0,0,0.3)] transition-transform duration-200"
                :class="[small ? 'size-[14px]' : 'size-[18px]', modelValue ? (small ? 'translate-x-[12px]' : 'translate-x-4') : '']"
            />
        </button>
        <span v-if="label" class="text-[12.5px] leading-tight">{{ label }}</span>
    </label>
</template>
