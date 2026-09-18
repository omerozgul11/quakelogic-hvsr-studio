<script setup lang="ts">
import { ref } from 'vue';
import { Play, RotateCcw, Download, Upload } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Field from '@/components/ui/Field.vue';
import Select from '@/components/ui/Select.vue';
import Toggle from '@/components/ui/Toggle.vue';
import HvsrParamsForm from '@/components/processing/HvsrParamsForm.vue';
import type { HvsrParams } from '@/api/types';
import type { SelectOption } from '@/components/ui/Select.vue';

export interface WindowsController {
    params: HvsrParams;
    fs: number | null;
    duration: number | null;
    runId: string | null;
    runOptions: SelectOption[];
    computing: boolean;
    errors: string[];
    overridesCount: number;
    freeSelect: boolean;
    hideSelected: boolean;
    commonY: boolean;
    compute: () => Promise<void>;
    resetOverrides: () => void;
    setRun: (id: string | null) => void;
    saveWindows: () => void;
    loadWindows: (file: File) => Promise<void>;
}
interface Props { ctl: WindowsController }
defineProps<Props>();
const fileInput = ref<HTMLInputElement | null>(null);
function pick(ctl: WindowsController, ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (f) void ctl.loadWindows(f);
    (ev.target as HTMLInputElement).value = '';
}
</script>

<template>
    <div class="flex flex-col h-full min-h-0">
        <div class="flex-1 overflow-auto scroll-thin p-4 space-y-5">
            <section class="space-y-2.5">
                <h3 class="eyebrow">Source</h3>
                <Field label="Analyse" hint="The raw recording or one of its saved processing runs."><Select :model-value="ctl.runId" :options="ctl.runOptions" @update:model-value="ctl.setRun($event === null ? null : String($event))" /></Field>
            </section>
            <HvsrParamsForm :params="ctl.params" :fs="ctl.fs" :duration="ctl.duration" windows-only />
            <section class="space-y-2.5">
                <h3 class="eyebrow">Display & selection</h3>
                <Toggle v-model="ctl.freeSelect" label="Free selection (draw windows)" small help="Drag a box across the traces to add a custom window. Switches the window mode to Custom on the first drawn window." />
                <Toggle v-model="ctl.hideSelected" label="Hide selected windows" small help="Hide the coloured overlays of accepted windows to inspect the signal." />
                <Toggle v-model="ctl.commonY" label="Common amplitude scale" small help="Use one amplitude scale for the three channels instead of per-channel auto scaling." />
                <div class="flex gap-2">
                    <Button size="sm" class="flex-1" title="Download the current window set as JSON" @click="ctl.saveWindows()"><Download class="size-3.5" />Save windows</Button>
                    <input ref="fileInput" type="file" accept=".json,application/json" class="hidden" @change="pick(ctl, $event)" />
                    <Button size="sm" class="flex-1" title="Load a saved window set (JSON)" @click="fileInput?.click()"><Upload class="size-3.5" />Load windows</Button>
                </div>
            </section>
            <ul v-if="ctl.errors.length" class="space-y-1 rounded-lg bg-bad-500/8 p-2.5"><li v-for="e in ctl.errors" :key="e" class="text-[11.5px] text-bad-500">{{ e }}</li></ul>
            <p class="help">Click a window in the plot or use the table to accept or reject it by hand. {{ ctl.overridesCount }} manual override{{ ctl.overridesCount === 1 ? '' : 's' }} are kept when parameters change and stored with the analysis.</p>
        </div>
        <div class="shrink-0 p-4 divider flex gap-2">
            <Button class="flex-1" size="lg" variant="primary" :loading="ctl.computing" :disabled="ctl.errors.length > 0" @click="ctl.compute()"><Play class="size-4" />Compute windows</Button>
            <Button size="lg" :disabled="ctl.overridesCount === 0" title="Clear manual accept/reject overrides" @click="ctl.resetOverrides()"><RotateCcw class="size-4" />{{ ctl.overridesCount }}</Button>
        </div>
    </div>
</template>
