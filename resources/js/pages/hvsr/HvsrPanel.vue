<script setup lang="ts">
import { computed, ref } from 'vue';
import { Play, Save } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Field from '@/components/ui/Field.vue';
import Select from '@/components/ui/Select.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Modal from '@/components/ui/Modal.vue';
import HvsrParamsForm from '@/components/processing/HvsrParamsForm.vue';
import type { HvsrParams } from '@/api/types';
import type { SelectOption } from '@/components/ui/Select.vue';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import { api } from '@/api';
import { mergeHvsrParams } from '@/components/processing/defaults';

export interface HvsrController {
    params: HvsrParams;
    name: string;
    seed: number | null;
    fs: number | null;
    duration: number | null;
    runId: string | null;
    runOptions: SelectOption[];
    overridesCount: number;
    errors: string[];
    running: boolean;
    run: () => Promise<void>;
    setRun: (id: string | null) => void;
}
interface Props { ctl: HvsrController }
const props = defineProps<Props>();
const store = useProjectStore();
const toast = useToastStore();

const presetId = ref<string | null>(null);
const presetOptions = computed(() => [{ value: null, label: 'Load HVSR parameters from preset…' }, ...store.presets.map((p) => ({ value: p.id, label: p.name }))]);
function loadPreset(id: string | number | null) {
    const p = store.presets.find((x) => x.id === id);
    if (!p) return;
    Object.assign(props.ctl.params, mergeHvsrParams(p.hvsr_params));
    presetId.value = null;
    toast.info('Parameters loaded', p.name);
}
const saveOpen = ref(false);
const presetName = ref('');
async function savePreset() {
    if (!store.current || !presetName.value.trim()) return;
    try {
        await api.projects.createPreset(store.current.id, { name: presetName.value.trim(), steps: [], hvsr_params: JSON.parse(JSON.stringify(props.ctl.params)) });
        await store.refresh();
        toast.success('Preset saved', presetName.value);
        saveOpen.value = false;
    } catch (e) { toast.error('Could not save preset', (e as Error).message); }
}
</script>

<template>
    <div class="flex flex-col h-full min-h-0">
        <div class="flex-1 overflow-auto scroll-thin p-4 space-y-5">
            <div class="flex items-center gap-2">
                <Select v-model="presetId" :options="presetOptions" @update:model-value="loadPreset" />
                <Button icon title="Save these parameters as a preset" @click="saveOpen = true"><Save class="size-4" /></Button>
            </div>
            <section class="space-y-2.5">
                <h3 class="eyebrow">Analysis</h3>
                <Field label="Name"><input v-model="ctl.name" class="input" /></Field>
                <Field label="Source" hint="Analyse the raw recording or one of its saved processing runs."><Select :model-value="ctl.runId" :options="ctl.runOptions" @update:model-value="ctl.setRun($event === null ? null : String($event))" /></Field>
                <p class="help">{{ ctl.overridesCount }} manual window override{{ ctl.overridesCount === 1 ? '' : 's' }} from Window selection.</p>
            </section>
            <HvsrParamsForm :params="ctl.params" :fs="ctl.fs" :duration="ctl.duration" />
            <section class="space-y-2.5">
                <h3 class="eyebrow">Reproducibility</h3>
                <Field label="Random seed" hint="Used for the bootstrap; leave empty to generate one (it is recorded with the result)."><NumberInput v-model="ctl.seed" :step="1" nullable placeholder="auto" /></Field>
            </section>
            <ul v-if="ctl.errors.length" class="space-y-1 rounded-lg bg-bad-500/8 p-2.5"><li v-for="e in ctl.errors" :key="e" class="text-[11.5px] text-bad-500">{{ e }}</li></ul>
        </div>
        <div class="shrink-0 p-4 divider">
            <Button class="w-full" size="lg" variant="primary" :loading="ctl.running" :disabled="ctl.errors.length > 0 || !ctl.name.trim()" @click="ctl.run()"><Play class="size-4" />Run analysis</Button>
        </div>
        <Modal :open="saveOpen" title="Save HVSR parameters as preset" @close="saveOpen = false">
            <Field label="Preset name"><input v-model="presetName" class="input" autofocus /></Field>
            <template #footer><Button @click="saveOpen = false">Cancel</Button><Button variant="primary" :disabled="!presetName.trim()" @click="savePreset">Save</Button></template>
        </Modal>
    </div>
</template>
