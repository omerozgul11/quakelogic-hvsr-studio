<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { Waves, Grid2x2, BarChart3, Check } from 'lucide-vue-next';
import { useNavigation, type StepKey } from '@/composables/useNavigation';
import { useProjectStore } from '@/stores/project';

const nav = useNavigation();
const router = useRouter();
const store = useProjectStore();

const steps = computed(() => {
    const rec = nav.recording.value;
    const hasAnalyses = (rec?.analyses?.length ?? 0) > 0;
    return [
        { key: 'waveforms' as StepKey, n: 1, label: 'Waveforms', icon: Waves, done: true, hint: 'Inspect and preprocess the recording' },
        { key: 'windows' as StepKey, n: 2, label: 'Windows', icon: Grid2x2, done: hasAnalyses, hint: 'Choose and screen the analysis windows' },
        { key: 'hvsr' as StepKey, n: 3, label: 'HVSR', icon: BarChart3, done: hasAnalyses, hint: 'Run and review the H/V analysis' },
    ];
});
const runName = computed(() => {
    const id = nav.runId.value;
    return id ? store.runs.find((r) => r.id === id)?.name ?? null : null;
});
</script>

<template>
    <div class="flex flex-wrap items-center gap-3">
        <div class="segmented" role="tablist" aria-label="Analysis steps">
            <button
                v-for="s in steps" :key="s.key" role="tab" class="seg-btn" :class="{ active: nav.step.value === s.key }" :title="s.hint"
                :aria-selected="nav.step.value === s.key" @click="router.push(nav.stepRoute(s.key))"
            >
                <span class="grid place-items-center size-4 rounded-full text-[10px] font-semibold" :class="nav.step.value === s.key ? 'bg-brand-500 text-white' : s.done ? 'bg-ok-500/15 text-ok-500' : 'bg-black/8 text-muted dark:bg-white/12'">
                    <Check v-if="s.done && nav.step.value !== s.key" class="size-2.5" /><template v-else>{{ s.n }}</template>
                </span>
                <component :is="s.icon" class="size-3.5 opacity-70" />{{ s.label }}
            </button>
        </div>
        <span class="text-[12px] text-faint truncate">Source: <span class="text-muted">{{ runName ?? 'raw recording' }}</span></span>
    </div>
</template>
