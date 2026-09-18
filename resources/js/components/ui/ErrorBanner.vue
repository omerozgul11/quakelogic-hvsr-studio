<script setup lang="ts">
import { AlertTriangle, PlugZap } from 'lucide-vue-next';
import { computed } from 'vue';
import { ApiError } from '@/api/client';

interface Props { error: unknown; title?: string }
const props = defineProps<Props>();
const emit = defineEmits<{ retry: [] }>();

const info = computed(() => {
    const e = props.error;
    if (!e) return null;
    if (e instanceof ApiError) {
        if (e.status === 503 || e.status === 0) {
            return {
                engine: true,
                title: props.title ?? (e.status === 0 ? 'Application server unreachable' : 'Processing engine is not running'),
                message: e.status === 0
                    ? 'The browser could not reach the local server. Start HVSR Studio with the launcher, then reload this page.'
                    : (e.hint ?? 'Start HVSR Studio with the launcher so the Python engine is running, or check the engine URL under Settings.'),
            };
        }
        const details = e.errors ? Object.values(e.errors).flat().join(' ') : '';
        return { engine: false, title: props.title ?? e.message, message: details };
    }
    return { engine: false, title: props.title ?? 'Something went wrong', message: String((e as Error).message ?? e) };
});
</script>

<template>
    <div v-if="info" class="rounded-md border px-3 py-2.5 flex gap-2.5 text-[12.5px]" :class="info.engine ? 'border-warn-500/40 bg-warn-500/8' : 'border-bad-500/40 bg-bad-500/6'">
        <component :is="info.engine ? PlugZap : AlertTriangle" class="size-4 mt-0.5 shrink-0" :class="info.engine ? 'text-warn-500' : 'text-bad-500'" />
        <div class="min-w-0 flex-1">
            <div class="font-medium">{{ info.title }}</div>
            <div v-if="info.message" class="text-muted mt-0.5 break-words">{{ info.message }}</div>
        </div>
        <button v-if="$attrs.onRetry" class="text-[12px] underline text-muted hover:text-ui self-start" @click="emit('retry')">Retry</button>
    </div>
</template>
