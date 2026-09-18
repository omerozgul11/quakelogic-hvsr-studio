<script setup lang="ts">
import { CheckCircle2, XCircle, MinusCircle } from 'lucide-vue-next';
import type { HvsrResult, SesameCriterion } from '@/api/types';
import Badge from '@/components/ui/Badge.vue';
import { fmtNum } from '@/utils/format';

interface Props { sesame: NonNullable<HvsrResult['sesame']> }
defineProps<Props>();
function fmt(v: number | string | null): string { return typeof v === 'number' ? fmtNum(v, 4) : (v ?? '—'); }
function icon(c: SesameCriterion) { return c.passed === null ? MinusCircle : c.passed ? CheckCircle2 : XCircle; }
function tone(c: SesameCriterion) { return c.passed === null ? 'text-faint' : c.passed ? 'text-ok-500' : 'text-bad-500'; }
</script>

<template>
    <div class="space-y-3 text-[12.5px]">
        <div class="flex flex-wrap gap-2">
            <Badge :tone="sesame.reliability_passed ? 'ok' : 'bad'">Reliable curve: {{ sesame.reliability_passed ? 'yes (3/3)' : 'no' }}</Badge>
            <Badge :tone="sesame.clarity_passed ? 'ok' : 'warn'">Clear peak: {{ sesame.clarity_passed_count }}/6 {{ sesame.clarity_passed ? '(≥5 fulfilled)' : '(fewer than 5)' }}</Badge>
        </div>
        <table class="table">
            <thead><tr><th></th><th>Criterion</th><th>Value</th><th>Threshold</th><th>Detail</th></tr></thead>
            <tbody>
                <tr><td colspan="5" class="text-[11px] uppercase tracking-wider text-faint font-semibold">Reliability of the H/V curve</td></tr>
                <tr v-for="c in sesame.reliability" :key="c.id">
                    <td><component :is="icon(c)" class="size-4" :class="tone(c)" /></td>
                    <td><span class="num text-faint mr-1">{{ c.id }}</span>{{ c.label }}</td>
                    <td class="num">{{ fmt(c.value) }}</td>
                    <td class="num">{{ fmt(c.threshold) }}</td>
                    <td class="text-muted text-[11.5px]">{{ c.detail }}</td>
                </tr>
                <tr><td colspan="5" class="text-[11px] uppercase tracking-wider text-faint font-semibold">Clarity of the H/V peak</td></tr>
                <tr v-for="c in sesame.clarity" :key="c.id">
                    <td><component :is="icon(c)" class="size-4" :class="tone(c)" /></td>
                    <td><span class="num text-faint mr-1">{{ c.id }}</span>{{ c.label }}</td>
                    <td class="num">{{ fmt(c.value) }}</td>
                    <td class="num">{{ fmt(c.threshold) }}</td>
                    <td class="text-muted text-[11.5px]">{{ c.detail }}</td>
                </tr>
            </tbody>
        </table>
        <p class="text-[11.5px] text-faint">Criteria evaluated as published in {{ sesame.reference }}. Fulfilling them describes the statistical robustness of the curve and peak; it does not by itself establish a site resonance.</p>
    </div>
</template>
