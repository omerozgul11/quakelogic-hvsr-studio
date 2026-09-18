<script setup lang="ts">
interface Props { title?: string; subtitle?: string; padded?: boolean; dense?: boolean; flat?: boolean }
withDefaults(defineProps<Props>(), { padded: true, dense: false, flat: false });
</script>

<template>
    <section class="flex flex-col min-w-0 overflow-hidden" :class="flat ? 'surface rounded-xl' : 'card'">
        <header v-if="title || $slots.actions" class="flex items-center justify-between gap-3 px-4 shrink-0" :class="dense ? 'h-10' : 'h-12'">
            <div class="min-w-0">
                <h2 class="section-title truncate">{{ title }}</h2>
                <p v-if="subtitle" class="text-[11px] text-faint truncate -mt-0.5">{{ subtitle }}</p>
            </div>
            <div class="flex items-center gap-2 shrink-0"><slot name="actions" /></div>
        </header>
        <div v-if="title || $slots.actions" class="divider mx-4" />
        <div :class="padded ? 'p-4' : ''" class="min-w-0 flex-1"><slot /></div>
    </section>
</template>
