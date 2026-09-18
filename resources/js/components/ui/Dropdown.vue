<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { ChevronDown } from 'lucide-vue-next';

interface Props { label: string; align?: 'left' | 'right'; size?: 'sm' | 'md'; variant?: 'secondary' | 'primary' | 'ghost' }
withDefaults(defineProps<Props>(), { align: 'right', size: 'md', variant: 'secondary' });
const open = ref(false);
const root = ref<HTMLElement | null>(null);

function onDoc(e: MouseEvent) {
    if (root.value && !root.value.contains(e.target as Node)) open.value = false;
}
onMounted(() => document.addEventListener('mousedown', onDoc));
onBeforeUnmount(() => document.removeEventListener('mousedown', onDoc));
defineExpose({ close: () => (open.value = false) });
</script>

<template>
    <div ref="root" class="relative inline-block">
        <button
            type="button"
            class="inline-flex items-center gap-1.5 font-medium transition whitespace-nowrap active:scale-[0.985]"
            :class="[
                size === 'sm' ? 'h-7 px-2.5 rounded-lg text-[12px]' : 'h-[34px] px-3.5 rounded-lg text-[13px]',
                variant === 'primary' ? 'bg-brand-600 text-white hover:bg-brand-700 dark:bg-brand-400 dark:text-brand-900' : variant === 'ghost' ? 'text-muted hover:bg-surface-2 hover:text-ui' : 'bg-surface text-ui border border-ui-strong hover:bg-surface-2',
            ]"
            :aria-expanded="open"
            @click="open = !open"
        >
            <slot name="icon" />{{ label }}<ChevronDown class="size-3.5 opacity-60" />
        </button>
        <Transition name="fade">
            <div v-if="open" class="absolute z-40 mt-1.5 min-w-48 bg-surface rounded-xl border border-ui py-1.5" style="box-shadow: var(--ui-shadow-lg)" :class="align === 'right' ? 'right-0' : 'left-0'" @click="open = false">
                <slot />
            </div>
        </Transition>
    </div>
</template>
