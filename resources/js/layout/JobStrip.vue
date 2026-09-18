<script setup lang="ts">
import { X } from 'lucide-vue-next';
import { useJobsStore } from '@/stores/jobs';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import Button from '@/components/ui/Button.vue';

const jobs = useJobsStore();
</script>

<template>
    <div v-if="jobs.active.length" class="shrink-0 surface border-x-0 border-t-0 px-3 py-1.5 flex flex-col gap-1.5">
        <div v-for="j in jobs.active" :key="j.key" class="flex items-center gap-3 text-[12px]">
            <span class="font-medium truncate max-w-64">{{ j.label }}</span>
            <span class="text-faint truncate flex-1">{{ j.message ?? (j.status === 'queued' ? 'Queued…' : 'Running…') }}</span>
            <div class="w-48"><ProgressBar :value="j.progress" :indeterminate="j.status === 'queued'" /></div>
            <span class="num text-faint w-10 text-right">{{ Math.round(j.progress * 100) }}%</span>
            <Button v-if="j.cancel" size="sm" variant="ghost" @click="jobs.cancel(j.key)">Cancel</Button>
        </div>
        <div v-for="j in jobs.recent.filter((r) => r.status === 'failed')" :key="j.key" class="flex items-center gap-3 text-[12px] text-bad-500">
            <span class="font-medium truncate max-w-64">{{ j.label }}</span>
            <span class="truncate flex-1">{{ j.error ?? 'failed' }}</span>
            <button class="p-0.5" @click="jobs.dismiss(j.key)"><X class="size-3.5" /></button>
        </div>
    </div>
</template>
