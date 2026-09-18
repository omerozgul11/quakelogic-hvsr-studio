<script setup lang="ts">
import { X } from 'lucide-vue-next';
import { onBeforeUnmount, onMounted } from 'vue';

interface Props { open: boolean; title: string; width?: string }
withDefaults(defineProps<Props>(), { width: 'max-w-lg' });
const emit = defineEmits<{ close: [] }>();

function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') emit('close');
}
onMounted(() => window.addEventListener('keydown', onKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
</script>

<template>
    <Teleport to="body">
        <Transition name="fade">
            <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/35 backdrop-blur-[2px] p-4" @mousedown.self="emit('close')">
                <div class="bg-surface rounded-2xl w-full flex flex-col max-h-[90vh]" :class="width" role="dialog" :aria-label="title" style="box-shadow: var(--ui-shadow-lg)">
                    <header class="flex items-center justify-between px-5 h-13 pt-1">
                        <h2 class="text-[15px] font-semibold">{{ title }}</h2>
                        <button class="text-faint hover:text-ui rounded-full p-1.5 hover:bg-surface-2" aria-label="Close" @click="emit('close')"><X class="size-4" /></button>
                    </header>
                    <div class="px-5 pb-4 overflow-auto scroll-thin text-[13px]"><slot /></div>
                    <footer v-if="$slots.footer" class="flex justify-end gap-2 px-5 py-4 divider"><slot name="footer" /></footer>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>
