<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { Moon, Sun, Monitor, PanelLeft, Settings, CircleHelp } from 'lucide-vue-next';
import { useGuideStore } from '@/stores/guide';
import { useAppStore } from '@/stores/app';
import { useProjectStore } from '@/stores/project';

interface Props { navCollapsed: boolean }
defineProps<Props>();
defineEmits<{ toggleNav: [] }>();

const app = useAppStore();
const project = useProjectStore();
const guide = useGuideStore();

const pill = computed(() => {
    if (app.statusError) return { cls: 'bg-bad-500/12 text-bad-500', dot: 'bg-bad-500' };
    if (!app.status) return { cls: 'bg-surface-2 text-muted', dot: 'bg-slate-400' };
    return app.engineOk ? { cls: 'bg-ok-500/12 text-ok-500', dot: 'bg-ok-500' } : { cls: 'bg-warn-500/15 text-warn-500', dot: 'bg-warn-500' };
});

function cycleTheme() {
    const next = app.theme === 'light' ? 'dark' : app.theme === 'dark' ? 'system' : 'light';
    app.setTheme(next);
}
const themeIcon = computed(() => (app.theme === 'light' ? Sun : app.theme === 'dark' ? Moon : Monitor));
</script>

<template>
    <header class="h-12 shrink-0 flex items-center gap-3 px-3 border-b border-ui backdrop-blur-md" style="background: var(--ui-sidebar)">
        <button class="text-faint hover:text-ui hover:bg-black/6 rounded-lg p-1.5 dark:hover:bg-white/10" title="Show or hide the sidebar" @click="$emit('toggleNav')"><PanelLeft class="size-4" /></button>
        <RouterLink to="/projects" class="flex items-center gap-2 select-none">
            <img :src="'/quakelogic-q-logo.png'" alt="QuakeLogic" width="26" height="26" class="size-[26px] rounded-[22%] object-contain shrink-0" />
            <span class="flex flex-col leading-none">
                <span class="font-extrabold tracking-tight text-[14px]">QuakeLogic</span>
                <span class="text-[9.5px] font-semibold uppercase tracking-[0.15em] text-muted">HVSR Studio</span>
            </span>
        </RouterLink>
        <template v-if="project.current">
            <span class="text-faint/60">/</span>
            <RouterLink :to="`/projects/${project.current.id}`" class="text-[13px] font-medium truncate max-w-72 rounded-md px-1.5 py-0.5 hover:bg-black/6 dark:hover:bg-white/10" title="Project overview">{{ project.current.name }}</RouterLink>
        </template>
        <div class="flex-1" />
        <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 h-6 text-[11.5px] font-medium" :class="pill.cls" :title="app.status?.engine?.message ?? app.statusError ?? ''">
            <span class="size-1.5 rounded-full" :class="pill.dot" />{{ app.engineLabel }}
            <span v-if="app.status?.engine?.engine_version" class="num text-faint">v{{ app.status.engine.engine_version }}</span>
        </span>
        <button class="text-faint hover:text-ui hover:bg-black/6 rounded-lg p-1.5 dark:hover:bg-white/10" :class="{ '!text-brand-600': guide.open }" title="Guided workflow (step-by-step help)" @click="guide.open ? guide.hide() : guide.show()"><CircleHelp class="size-4" /></button>
        <button class="text-faint hover:text-ui hover:bg-black/6 rounded-lg p-1.5 dark:hover:bg-white/10" :title="`Theme: ${app.theme} (click to change)`" @click="cycleTheme"><component :is="themeIcon" class="size-4" /></button>
        <RouterLink to="/settings" class="text-faint hover:text-ui hover:bg-black/6 rounded-lg p-1.5 dark:hover:bg-white/10" title="Settings"><Settings class="size-4" /></RouterLink>
    </header>
</template>
