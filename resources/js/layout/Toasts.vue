<script setup lang="ts">
import { CheckCircle2, Info, AlertTriangle, XCircle, X } from 'lucide-vue-next';
import { useToastStore } from '@/stores/toast';

const store = useToastStore();
const icons = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: XCircle };
const tones = { info: 'text-brand-500', success: 'text-ok-500', warning: 'text-warn-500', error: 'text-bad-500' };
</script>

<template>
    <Teleport to="body">
        <div class="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 w-80">
            <TransitionGroup name="fade">
                <div v-for="t in store.toasts" :key="t.id" class="surface rounded-lg shadow-lg p-3 flex gap-2.5 text-[12.5px]">
                    <component :is="icons[t.kind]" class="size-4 shrink-0 mt-0.5" :class="tones[t.kind]" />
                    <div class="min-w-0 flex-1">
                        <div class="font-medium">{{ t.title }}</div>
                        <div v-if="t.message" class="text-muted mt-0.5 break-words">{{ t.message }}</div>
                    </div>
                    <button class="text-faint hover:text-ui self-start" @click="store.dismiss(t.id)"><X class="size-3.5" /></button>
                </div>
            </TransitionGroup>
        </div>
    </Teleport>
</template>
