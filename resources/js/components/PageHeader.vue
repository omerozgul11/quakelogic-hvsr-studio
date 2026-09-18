<script setup lang="ts">
import { ChevronLeft, ChevronRight } from 'lucide-vue-next';
import { RouterLink, useRouter } from 'vue-router';
import { useNavigation } from '@/composables/useNavigation';
import StepSwitcher from './StepSwitcher.vue';

interface Props { title: string; subtitle?: string; steps?: boolean; noBack?: boolean; noCrumbs?: boolean }
withDefaults(defineProps<Props>(), { steps: false, noBack: false, noCrumbs: false });
const nav = useNavigation();
const router = useRouter();
</script>

<template>
    <header class="mb-5">
        <div v-if="!noCrumbs && nav.crumbs.value.length > 1" class="flex items-center gap-1 text-[12px] text-faint mb-2 min-w-0">
            <template v-for="(c, i) in nav.crumbs.value" :key="i">
                <RouterLink v-if="c.to && i < nav.crumbs.value.length - 1" :to="c.to" class="hover:text-ui truncate max-w-56">{{ c.label }}</RouterLink>
                <span v-else class="truncate max-w-64 text-muted">{{ c.label }}</span>
                <ChevronRight v-if="i < nav.crumbs.value.length - 1" class="size-3 shrink-0" />
            </template>
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
            <button
                v-if="!noBack && nav.parent.value"
                class="inline-flex items-center gap-0.5 h-8 pl-1.5 pr-3 rounded-lg text-[13px] text-brand-700 hover:bg-brand-500/10 dark:text-brand-300 -ml-1.5"
                :title="`Back to ${nav.parent.value.label}`"
                @click="router.push(nav.parent.value!.to)"
            >
                <ChevronLeft class="size-4" /><span class="truncate max-w-40">{{ nav.parent.value.label }}</span>
            </button>
            <div class="min-w-0 flex-1 basis-80">
                <h1 class="page-title truncate flex items-center gap-2"><slot name="title">{{ title }}</slot></h1>
                <p v-if="subtitle || $slots.subtitle" class="text-[12.5px] text-muted mt-0.5 truncate"><slot name="subtitle">{{ subtitle }}</slot></p>
            </div>
            <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2 ml-auto"><slot name="actions" /></div>
        </div>
        <div v-if="steps && nav.recordingId.value" class="mt-4"><StepSwitcher /></div>
        <slot name="below" />
    </header>
</template>
