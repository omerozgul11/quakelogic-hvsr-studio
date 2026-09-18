<script setup lang="ts">
import { onMounted } from 'vue';
import GuideWizard from '@/components/GuideWizard.vue';
import { useGuideStore } from '@/stores/guide';
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import TopBar from './TopBar.vue';
import Navigator from './Navigator.vue';
import ProcessingPanel from './ProcessingPanel.vue';
import JobStrip from './JobStrip.vue';
import Toasts from './Toasts.vue';
import { providePanelHost } from '@/composables/usePanel';
import { useResizable } from '@/composables/useResizable';
import { useAppStore } from '@/stores/app';
import { ref } from 'vue';

const app = useAppStore();
const route = useRoute();
const panel = providePanelHost();

const navCollapsed = ref(false);
const nav = useResizable({ min: 240, max: 440, initial: 300, storageKey: 'hvsr-nav-width', side: 'left' });
const side = useResizable({ min: 320, max: 560, initial: 384, storageKey: 'hvsr-panel-width', side: 'right' });

const showPanel = computed(() => panel.content.value !== null && !panel.collapsed.value);
const pageKey = computed(() => String(route.name ?? '') + ':' + JSON.stringify(route.params));
const guideStore = useGuideStore();
onMounted(() => guideStore.autoOpen());
</script>

<template>
    <div class="h-full flex flex-col bg-ui text-ui" :class="{ dark: app.isDark }">
        <TopBar :nav-collapsed="navCollapsed" @toggle-nav="navCollapsed = !navCollapsed" />
        <JobStrip />
        <div class="flex-1 flex min-h-0">
            <aside
                v-show="!navCollapsed"
                class="shrink-0 flex flex-col min-h-0 border-r border-ui backdrop-blur-md"
                :style="{ width: nav.size.value + 'px', background: 'var(--ui-sidebar)' }"
            >
                <Navigator />
            </aside>
            <div v-show="!navCollapsed" class="splitter" :class="{ active: nav.dragging.value }" @pointerdown="nav.onPointerDown" />

            <main class="flex-1 min-w-0 min-h-0 overflow-auto scroll-thin">
                <RouterView :key="pageKey" />
            </main>

            <template v-if="panel.content.value">
                <div v-show="showPanel" class="splitter" :class="{ active: side.dragging.value }" @pointerdown="side.onPointerDown" />
                <aside
                    class="shrink-0 flex flex-col min-h-0 border-l border-ui backdrop-blur-md"
                    :style="{ width: showPanel ? side.size.value + 'px' : '40px', background: 'var(--ui-sidebar)' }"
                >
                    <ProcessingPanel />
                </aside>
            </template>
        </div>
        <Toasts />
        <GuideWizard />
    </div>
</template>
