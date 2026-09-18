<script setup lang="ts">
import { inject } from 'vue';
import { PanelRightClose, PanelRightOpen } from 'lucide-vue-next';
import { PanelKey } from '@/composables/usePanel';

const host = inject(PanelKey)!;
</script>

<template>
    <div class="flex flex-col h-full min-h-0">
        <div class="h-12 flex items-center border-b border-ui shrink-0" :class="host.collapsed.value ? 'justify-center' : 'px-3 gap-2'">
            <button class="text-faint hover:text-ui hover:bg-black/6 rounded-lg p-1.5 dark:hover:bg-white/10" :title="host.collapsed.value ? 'Expand panel' : 'Collapse panel'" @click="host.collapsed.value = !host.collapsed.value">
                <component :is="host.collapsed.value ? PanelRightOpen : PanelRightClose" class="size-4" />
            </button>
            <h2 v-if="!host.collapsed.value" class="text-[13px] font-semibold truncate">{{ host.content.value?.title }}</h2>
        </div>
        <div v-if="!host.collapsed.value && host.content.value" class="flex-1 min-h-0 overflow-auto scroll-thin">
            <component :is="host.content.value.component" v-bind="host.content.value.props ?? {}" />
        </div>
        <div v-else-if="host.collapsed.value" class="flex-1 grid place-items-start justify-center pt-3">
            <span class="text-[10.5px] text-faint uppercase tracking-wider" style="writing-mode: vertical-rl">{{ host.content.value?.title }}</span>
        </div>
    </div>
</template>
