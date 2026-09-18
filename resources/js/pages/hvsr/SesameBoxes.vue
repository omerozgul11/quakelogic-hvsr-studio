<script setup lang="ts">
import type { HvsrResult } from '@/api/types';

/** QLExplorer-style SESAME summary: Curve I–III (reliability), Peak I–VI (clarity), Overall. */
interface Props { sesame: NonNullable<HvsrResult['sesame']> }
defineProps<Props>();
const roman = ['I', 'II', 'III', 'IV', 'V', 'VI'];
function tone(passed: boolean | null): string {
    return passed === null ? 'bg-surface-2 text-faint border-ui' : passed ? 'bg-[#22c55e] text-white border-[#16a34a]' : 'bg-[#ef4444] text-white border-[#dc2626]';
}
</script>

<template>
    <div class="card p-3 text-center text-[12px] w-[108px] shrink-0">
        <div class="font-semibold leading-tight">SESAME<br /><span class="text-faint font-normal">criteria</span></div>
        <div class="mt-2 eyebrow">Curve</div>
        <div class="mt-1 flex flex-col items-center gap-1">
            <span v-for="(c, i) in sesame.reliability" :key="c.id" class="grid place-items-center w-9 h-7 rounded-md border font-semibold num" :class="tone(c.passed)" :title="`${c.label}: ${c.detail ?? ''}`">{{ roman[i] }}</span>
        </div>
        <div class="mt-2 eyebrow">Peak</div>
        <div class="mt-1 flex flex-col items-center gap-1">
            <span v-for="(c, i) in sesame.clarity" :key="c.id" class="grid place-items-center w-9 h-7 rounded-md border font-semibold num" :class="tone(c.passed)" :title="`${c.label}: ${c.detail ?? ''}`">{{ roman[i] }}</span>
        </div>
        <div class="mt-2 eyebrow">Overall</div>
        <div class="mt-1 flex justify-center"><span class="grid place-items-center w-9 h-9 rounded-md border" :class="tone(sesame.reliability_passed && sesame.clarity_passed)" :title="`Reliable: ${sesame.reliability_passed ? 'yes' : 'no'} · clear peak: ${sesame.clarity_passed_count}/6`" /></div>
    </div>
</template>
