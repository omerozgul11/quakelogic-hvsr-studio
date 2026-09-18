<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { X, ChevronLeft, ChevronRight, Check, ArrowRight, BookOpen, Circle } from 'lucide-vue-next';
import { useGuideStore } from '@/stores/guide';
import Button from '@/components/ui/Button.vue';

const guide = useGuideStore();
const router = useRouter();
const isLast = computed(() => guide.step >= guide.steps.length - 1);

function openStep() {
    const s = guide.current;
    if (s.route) router.push(s.route);
}
function openManual() {
    router.push({ path: '/manual', query: { doc: 'user-guide' }, hash: `#${guide.current.docAnchor}` });
}
</script>

<template>
    <Transition name="fade">
        <section
            v-if="guide.open"
            class="fixed bottom-5 right-5 z-40 w-[380px] max-w-[calc(100vw-2.5rem)] bg-surface rounded-2xl border border-ui overflow-hidden" style="box-shadow: var(--ui-shadow-lg)"
            role="dialog" aria-label="Guided workflow"
        >
            <header class="flex items-center gap-2 px-4 pt-3.5 pb-1">
                <span class="text-[13px] font-semibold">Guided workflow</span>
                <span class="text-[11px] text-faint">step {{ guide.step + 1 }} of {{ guide.steps.length }} · {{ guide.completed }} done</span>
                <div class="flex-1" />
                <button class="rounded-full p-1.5 text-faint hover:text-ui hover:bg-surface-2" title="Close" @click="guide.hide()"><X class="size-4" /></button>
            </header>

            <div class="px-4 pt-3 flex gap-1.5 flex-wrap">
                <button
                    v-for="(s, i) in guide.steps" :key="s.key"
                    class="grid place-items-center size-6 rounded-full text-[10.5px] font-medium transition"
                    :class="i === guide.step ? 'bg-brand-500 text-white' : s.done ? 'bg-ok-500/15 text-ok-500' : 'bg-black/6 text-muted hover:bg-black/10 dark:bg-white/10'"
                    :title="s.title" @click="guide.goTo(i)"
                ><Check v-if="s.done && i !== guide.step" class="size-3" /><template v-else>{{ i + 1 }}</template></button>
            </div>

            <div class="px-4 py-3">
                <div class="flex items-start gap-2">
                    <span class="mt-0.5 grid place-items-center size-5 rounded-full shrink-0" :class="guide.current.done ? 'bg-ok-500/15 text-ok-500' : 'bg-surface-2 text-faint'">
                        <Check v-if="guide.current.done" class="size-3" /><Circle v-else class="size-3" />
                    </span>
                    <div class="min-w-0">
                        <h3 class="text-[13.5px] font-semibold leading-tight">{{ guide.current.title }} <span v-if="guide.current.optional" class="text-[11px] font-normal text-faint">(optional)</span></h3>
                        <p class="text-[12.5px] text-muted mt-1">{{ guide.current.summary }}</p>
                    </div>
                </div>
                <ul class="mt-2.5 ml-7 space-y-1 text-[12px] text-muted list-disc">
                    <li v-for="(t, i) in guide.current.tips" :key="i">{{ t }}</li>
                </ul>
                <p v-if="guide.current.done" class="mt-2.5 ml-7 text-[12px] text-ok-500 flex items-center gap-1"><Check class="size-3.5" /> Already done in this project.</p>
                <p v-else-if="guide.current.blocked" class="mt-2.5 ml-7 text-[12px] text-warn-500">{{ guide.current.blocked }}</p>
                <div class="mt-3 ml-7 flex flex-wrap items-center gap-2">
                    <Button variant="primary" size="sm" :disabled="!guide.current.route" @click="openStep"><ArrowRight class="size-3.5" /> {{ guide.current.routeLabel }}</Button>
                    <Button size="sm" @click="openManual"><BookOpen class="size-3.5" /> Read in the manual</Button>
                </div>
            </div>

            <footer class="flex items-center gap-2 px-4 py-3 divider">
                <label class="flex items-center gap-1.5 text-[11.5px] text-muted select-none">
                    <input type="checkbox" :checked="guide.dismissed" @change="guide.dismiss(($event.target as HTMLInputElement).checked)" /> Don't open automatically
                </label>
                <div class="flex-1" />
                <Button size="sm" :disabled="guide.step === 0" @click="guide.back()"><ChevronLeft class="size-3.5" /> Back</Button>
                <Button v-if="!isLast" size="sm" variant="primary" @click="guide.next()">Next <ChevronRight class="size-3.5" /></Button>
                <Button v-else size="sm" variant="primary" @click="guide.hide()">Finish</Button>
            </footer>
        </section>
    </Transition>
</template>
