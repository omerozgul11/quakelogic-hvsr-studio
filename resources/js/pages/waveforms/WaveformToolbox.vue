<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Play, Save, FolderDown, Eye } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Field from '@/components/ui/Field.vue';
import Select from '@/components/ui/Select.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Modal from '@/components/ui/Modal.vue';
import StepList from '@/components/processing/StepList.vue';
import FilterResponsePlot from '@/components/plots/FilterResponsePlot.vue';
import { api } from '@/api';
import type { FilterResponse, Step } from '@/api/types';
import type { WaveformController } from './controller';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import { defaultHvsrParams } from '@/components/processing/defaults';

interface Props { ctl: WaveformController }
const props = defineProps<Props>();
const store = useProjectStore();
const toast = useToastStore();

const selected = ref<number | null>(null);
const response = ref<FilterResponse | null>(null);
const responseError = ref<string | null>(null);
let respTimer: number | null = null;

const selectedStep = computed<Step | null>(() => (selected.value !== null ? props.ctl.steps[selected.value] ?? null : null));
const showsResponse = computed(() => !!selectedStep.value && (selectedStep.value.op === 'filter' || selectedStep.value.op === 'notch'));

async function fetchResponse() {
    const s = selectedStep.value;
    if (!s || !showsResponse.value || !props.ctl.fs) { response.value = null; return; }
    try {
        response.value = await api.app.filterResponse(props.ctl.fs, JSON.parse(JSON.stringify(s)));
        responseError.value = null;
    } catch (e) { responseError.value = (e as Error).message; response.value = null; }
}
watch([selectedStep, () => JSON.stringify(selectedStep.value?.params)], () => {
    if (respTimer) window.clearTimeout(respTimer);
    respTimer = window.setTimeout(() => void fetchResponse(), 300);
}, { immediate: true });

const presetId = ref<string | null>(null);
const presetOptions = computed(() => [{ value: null, label: 'Load preset…' }, ...store.presets.map((p) => ({ value: p.id, label: p.name }))]);
function loadPreset(id: string | number | null) {
    const p = store.presets.find((x) => x.id === id);
    if (!p) return;
    props.ctl.steps.splice(0, props.ctl.steps.length, ...JSON.parse(JSON.stringify(p.steps ?? [])));
    presetId.value = null;
    props.ctl.onChange();
    toast.info('Preset loaded', p.name);
}
const saveOpen = ref(false);
const presetName = ref('');
async function savePreset() {
    if (!store.current || !presetName.value.trim()) return;
    try {
        await api.projects.createPreset(store.current.id, { name: presetName.value.trim(), steps: JSON.parse(JSON.stringify(props.ctl.steps)), hvsr_params: defaultHvsrParams() });
        await store.refresh();
        toast.success('Preset saved', presetName.value);
        saveOpen.value = false;
        presetName.value = '';
    } catch (e) { toast.error('Could not save preset', (e as Error).message); }
}
const runOpen = ref(false);
const runName = ref('');
</script>

<template>
    <div class="flex flex-col h-full min-h-0">
        <div class="flex-1 overflow-auto scroll-thin p-4 space-y-5">
        <div class="flex items-center gap-2">
            <Select v-model="presetId" :options="presetOptions" @update:model-value="loadPreset" />
            <Button icon title="Save these steps as a preset" :disabled="ctl.steps.length === 0" @click="saveOpen = true"><Save class="size-4" /></Button>
        </div>

        <StepList :steps="ctl.steps" :fs="ctl.fs" :duration="ctl.duration" :warnings="ctl.warnings" :selected-index="selected" @change="ctl.onChange()" @select="selected = $event" @reset="ctl.reset()" />

        <div v-if="showsResponse" class="rounded-xl bg-surface-2 p-2.5">
            <div class="eyebrow mb-1">Filter response (dotted: −3 dB)</div>
            <FilterResponsePlot :response="response" />
            <p v-if="responseError" class="text-[11.5px] text-bad-500">{{ responseError }}</p>
            <ul v-if="response?.warnings?.length" class="mt-1 space-y-0.5">
                <li v-for="(w, i) in response.warnings" :key="i" class="text-[11.5px] text-warn-500">{{ w.message }}</li>
            </ul>
        </div>

        <div v-if="ctl.warnings.filter((w) => w.step_index === null).length" class="space-y-1 rounded-lg bg-warn-500/10 p-2.5">
            <p v-for="(w, i) in ctl.warnings.filter((w) => w.step_index === null)" :key="i" class="text-[11.5px] text-warn-500">{{ w.message }}</p>
        </div>
        </div>

        <div class="shrink-0 p-4 divider space-y-2.5">
            <Toggle v-model="ctl.autoPreview" label="Preview automatically" small help="Apply the steps in memory for the visible range whenever a parameter changes." />
            <div class="flex gap-2">
                <Button class="flex-1" :loading="ctl.previewing" :disabled="ctl.steps.length === 0" title="Apply the steps in memory for the visible range" @click="ctl.preview()"><Eye class="size-4" />Preview</Button>
                <Button class="flex-1" variant="primary" :disabled="ctl.steps.filter((s) => s.enabled).length === 0" title="Store the processed record as a named run" @click="runName = ctl.suggestRunName(); runOpen = true"><Play class="size-4" />Run & save</Button>
            </div>
        </div>

        <Modal :open="saveOpen" title="Save processing preset" @close="saveOpen = false">
            <Field label="Preset name"><input v-model="presetName" class="input" autofocus /></Field>
            <p class="help">Presets store the ordered processing steps and can be applied in batch runs.</p>
            <template #footer><Button @click="saveOpen = false">Cancel</Button><Button variant="primary" :disabled="!presetName.trim()" @click="savePreset"><FolderDown class="size-4" />Save</Button></template>
        </Modal>
        <Modal :open="runOpen" title="Run processing and save" @close="runOpen = false">
            <Field label="Run name"><input v-model="runName" class="input" autofocus /></Field>
            <p class="help">{{ ctl.steps.filter((s) => s.enabled).length }} enabled step(s) will be applied to the full record and stored with every parameter for reproducibility.</p>
            <template #footer><Button @click="runOpen = false">Cancel</Button><Button variant="primary" :disabled="!runName.trim()" @click="ctl.run(runName); runOpen = false">Run</Button></template>
        </Modal>
    </div>
</template>
