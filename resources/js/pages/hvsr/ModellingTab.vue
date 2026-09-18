<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { ArrowUp, ArrowDown, Trash2, Plus, Play, Save, FolderOpen } from 'lucide-vue-next';
import { api } from '@/api';
import type { CurveSet, GroundModel, ModelLayer, ModelResponse, Ulid } from '@/api/types';
import { useToastStore } from '@/stores/toast';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import Select from '@/components/ui/Select.vue';
import Modal from '@/components/ui/Modal.vue';
import ModelPlot from '@/components/plots/ModelPlot.vue';
import ProfilePlot from '@/components/plots/ProfilePlot.vue';
import { fmtNum } from '@/utils/format';

interface Props { analysisId: Ulid; frequency: number[]; curve: CurveSet | null; models: GroundModel[] }
const props = defineProps<Props>();
const emit = defineEmits<{ modelsChanged: [models: GroundModel[]] }>();
const toast = useToastStore();

function poissonFrom(vp: number | null, vs: number): number | null {
    if (!vp || vp <= vs * Math.SQRT2) return null;
    const r2 = (vp / vs) ** 2;
    return (r2 - 2) / (2 * (r2 - 1));
}
function vpFrom(nu: number | null, vs: number): number | null {
    if (nu === null || nu <= 0 || nu >= 0.5) return null;
    return vs * Math.sqrt((2 - 2 * nu) / (1 - 2 * nu));
}
function layer(thickness: number | null, vs: number, vp: number, density: number): ModelLayer {
    return { thickness_m: thickness, vs, vp, poisson: poissonFrom(vp, vs), density, qs: 30, qp: 60 };
}
const layers = reactive<ModelLayer[]>([layer(50, 155, 320, 1800), layer(8, 120, 250, 2000), layer(null, 450, 800, 2200)]);
const freqMin = ref(0.2);
const freqMax = ref(100);
const nFreq = ref(200);
const vs30Offset = ref(0);
const model = ref<ModelResponse | null>(null);
const busy = ref(false);
const showProfile = ref(true);
const showExp = ref(true);
const showStd = ref(true);
const showSyn = ref(true);
const link = ref<'none' | 'experimental' | 'synthetic' | 'common'>('none');
const manualFreq = ref(false);
const manualRatio = ref(false);
const fr = reactive<{ min: number | null; max: number | null }>({ min: 0.2, max: 25 });
const rr = reactive<{ min: number | null; max: number | null }>({ min: 0, max: 10 });

const depths = computed(() => { let z = 0; return layers.map((l) => { const top = z; z += l.thickness_m ?? 0; return { top, bottom: l.thickness_m === null ? null : z }; }); });

function onVs(i: number, v: number | null) { const l = layers[i]; if (v === null || v <= 0) return; l.vs = v; if (l.poisson !== null) l.vp = vpFrom(l.poisson, v); else l.poisson = poissonFrom(l.vp, v); }
function onVp(i: number, v: number | null) { const l = layers[i]; l.vp = v; l.poisson = poissonFrom(v, l.vs); }
function onPoisson(i: number, v: number | null) { const l = layers[i]; l.poisson = v; l.vp = vpFrom(v, l.vs); }
function move(i: number, d: -1 | 1) { const j = i + d; if (j < 0 || j >= layers.length - 1 || i >= layers.length - 1) return; const t = layers[i]; layers[i] = layers[j]; layers[j] = t; }
function remove(i: number) { if (layers.length <= 2 || i === layers.length - 1) return; layers.splice(i, 1); }
function add() { const half = layers[layers.length - 1]; layers.splice(layers.length - 1, 0, layer(10, Math.round(half.vs * 0.6), Math.round((half.vp ?? half.vs * 2) * 0.6), half.density)); }

async function generate() {
    busy.value = true;
    try {
        model.value = await api.app.modelHvsr({ layers: JSON.parse(JSON.stringify(layers)), freq_min: freqMin.value, freq_max: freqMax.value, n_freq: nFreq.value, vs30_offset_m: vs30Offset.value });
        model.value.layers.forEach((l, i) => { if (layers[i]) { layers[i].vp = l.vp ?? layers[i].vp; layers[i].poisson = l.poisson ?? layers[i].poisson; } });
    } catch (e) { toast.error('Model computation failed', (e as Error).message); } finally { busy.value = false; }
}
const misfit = computed(() => {
    const m = model.value;
    const c = props.curve;
    if (!m || !c) return null;
    const lf = m.frequency.map(Math.log10);
    const lv = m.hvsr.map((v) => (v === null || v <= 0 ? NaN : Math.log(v)));
    let sum = 0;
    let n = 0;
    props.frequency.forEach((f, i) => {
        const y = c.values[i];
        if (y === null || y <= 0 || f < m.frequency[0] || f > m.frequency[m.frequency.length - 1]) return;
        const x = Math.log10(f);
        let k = 0;
        while (k < lf.length - 2 && lf[k + 1] < x) k++;
        const t = (x - lf[k]) / Math.max(1e-12, lf[k + 1] - lf[k]);
        const lm = lv[k] + (lv[k + 1] - lv[k]) * t;
        if (!Number.isFinite(lm)) return;
        sum += (lm - Math.log(y)) ** 2;
        n += 1;
    });
    return n ? Math.sqrt(sum / n) : null;
});

// saved models
const saveOpen = ref(false);
const modelName = ref('');
const loadId = ref<string | null>(null);
const loadOptions = computed(() => [{ value: null, label: 'Load a saved model…' }, ...props.models.map((m) => ({ value: m.id, label: m.name }))]);
async function saveModel() {
    if (!modelName.value.trim()) return;
    const next: GroundModel[] = [...props.models, { id: `m${Date.now().toString(36)}`, name: modelName.value.trim(), layers: JSON.parse(JSON.stringify(layers)), vs30_offset_m: vs30Offset.value, created_at: new Date().toISOString() }];
    try { const res = await api.analyses.saveModels(props.analysisId, next); emit('modelsChanged', res.models ?? next); toast.success('Model saved', modelName.value); saveOpen.value = false; modelName.value = ''; }
    catch (e) { toast.error('Could not save model', (e as Error).message); }
}
function loadModel(id: string | number | null) {
    const m = props.models.find((x) => x.id === id);
    if (!m) return;
    layers.splice(0, layers.length, ...JSON.parse(JSON.stringify(m.layers)) as ModelLayer[]);
    vs30Offset.value = m.vs30_offset_m ?? 0;
    loadId.value = null;
    void generate();
}
async function deleteModel(id: string) {
    const next = props.models.filter((m) => m.id !== id);
    try { const res = await api.analyses.saveModels(props.analysisId, next); emit('modelsChanged', res.models ?? next); } catch (e) { toast.error('Could not delete model', (e as Error).message); }
}
watch(() => props.curve, (c) => { if (c && props.frequency.length) { freqMin.value = Number(props.frequency[0].toPrecision(3)); freqMax.value = Number(props.frequency[props.frequency.length - 1].toPrecision(3)); } }, { immediate: true });
</script>

<template>
    <div class="space-y-4">
        <div class="grid grid-cols-1 2xl:grid-cols-[minmax(0,1fr)_420px] gap-4">
            <Panel title="Ground model" :padded="false">
                <template #actions>
                    <Select v-model="loadId" :options="loadOptions" @update:model-value="loadModel" />
                    <Button size="sm" title="Save this model with the analysis" @click="saveOpen = true"><Save class="size-3.5" />Save</Button>
                </template>

<style scoped>
.model-table :deep(.input) { height: 30px; padding: 0 6px; font-size: 12px; }
.model-table td { padding-top: 4px; padding-bottom: 4px; }
</style>
                <div class="overflow-auto scroll-thin">
                    <table class="table min-w-[760px] model-table">
                        <thead><tr><th>#</th><th>H (m)</th><th>D (m)</th><th>Vp (m/s)</th><th>Vs (m/s)</th><th>Poisson</th><th>ρ (kg/m³)</th><th>Qs</th><th>Qp</th><th></th></tr></thead>
                        <tbody>
                            <tr v-for="(l, i) in layers" :key="i">
                                <td class="num">{{ i + 1 }}</td>
                                <td class="w-24"><span v-if="i === layers.length - 1" class="text-faint whitespace-nowrap">half-space</span><NumberInput v-else v-model="l.thickness_m" :min="0.1" /></td>
                                <td class="num text-muted">{{ depths[i].bottom === null ? `> ${fmtNum(depths[i].top, 4)}` : fmtNum(depths[i].bottom, 4) }}</td>
                                <td class="w-24"><NumberInput :model-value="l.vp" :min="1" nullable @update:model-value="onVp(i, $event)" /></td>
                                <td class="w-24"><NumberInput :model-value="l.vs" :min="1" @update:model-value="onVs(i, $event)" /></td>
                                <td class="w-24"><NumberInput :model-value="l.poisson" :min="0" :max="0.499" :step="0.01" nullable @update:model-value="onPoisson(i, $event)" /></td>
                                <td class="w-24"><NumberInput v-model="l.density" :min="100" /></td>
                                <td class="w-20"><NumberInput :model-value="l.qs ?? null" :min="1" nullable @update:model-value="l.qs = $event" /></td>
                                <td class="w-20"><NumberInput :model-value="l.qp ?? null" :min="1" nullable @update:model-value="l.qp = $event" /></td>
                                <td class="whitespace-nowrap">
                                    <Button icon size="xs" variant="ghost" title="Layer up" :disabled="i === 0 || i === layers.length - 1" @click="move(i, -1)"><ArrowUp class="size-3.5" /></Button>
                                    <Button icon size="xs" variant="ghost" title="Layer down" :disabled="i >= layers.length - 2" @click="move(i, 1)"><ArrowDown class="size-3.5" /></Button>
                                    <Button icon size="xs" variant="ghost" title="Remove layer" :disabled="i === layers.length - 1 || layers.length <= 2" @click="remove(i)"><Trash2 class="size-3.5" /></Button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div class="flex flex-wrap items-center gap-2 p-3 divider">
                    <Button size="sm" @click="add"><Plus class="size-3.5" />Add layer</Button>
                    <Toggle v-model="showProfile" label="Show profile" small />
                    <div class="flex-1" />
                    <span class="text-[12px] text-muted">Poisson's ratio ν = (r²−2)/(2(r²−1)), r = Vp/Vs; editing Vs, Vp or ν keeps the others consistent.</span>
                </div>
            </Panel>
            <div class="space-y-4">
                <Panel title="Synthetic curve">
                    <div class="grid grid-cols-2 gap-2.5">
                        <Field label="Frequency from"><NumberInput v-model="freqMin" :min="0.01" unit="Hz" /></Field>
                        <Field label="to"><NumberInput v-model="freqMax" :min="0.1" unit="Hz" /></Field>
                        <Field label="Number of points"><NumberInput v-model="nFreq" :min="20" :max="2000" :step="10" /></Field>
                        <Field label="Vs30 offset" hint="Depth below which the 30 m average starts (e.g. a planned excavation)."><NumberInput v-model="vs30Offset" :min="0" unit="m" /></Field>
                    </div>
                    <Button class="mt-3 w-full" variant="primary" :loading="busy" @click="generate"><Play class="size-4" />Generate</Button>
                    <dl v-if="model" class="mt-3 grid grid-cols-[110px_1fr] gap-y-1 text-[12.5px]">
                        <dt class="text-muted">Vs30</dt><dd class="num">{{ fmtNum(model.vs30, 4) }} m/s</dd>
                        <dt class="text-muted">VsEq</dt><dd class="num">{{ fmtNum(model.vseq?.value, 4) }} m/s <span class="text-faint" v-if="model.vseq?.depth_m">(to {{ fmtNum(model.vseq.depth_m, 4) }} m)</span></dd>
                        <dt class="text-muted">Model f0</dt><dd class="num">{{ fmtNum(model.f0_model, 4) }} Hz</dd>
                        <dt class="text-muted">Misfit</dt><dd class="num">{{ misfit === null ? '—' : fmtNum(misfit, 3) }} <span class="text-faint">RMS of ln(model / experimental) over the common range</span></dd>
                    </dl>
                    <p v-if="model" class="help mt-2">{{ model.method }}</p>
                </Panel>
                <Panel title="Plot options">
                    <div class="grid grid-cols-2 gap-x-4 gap-y-2">
                        <Toggle v-model="showExp" label="Experimental curve" small />
                        <Toggle v-model="showStd" label="Standard deviation curves" small />
                        <Toggle v-model="showSyn" label="Synthetic curve" small />
                        <Field label="Link frequencies to"><Select v-model="link" :options="[{ value: 'none', label: 'Nothing' }, { value: 'experimental', label: 'Experimental curve' }, { value: 'synthetic', label: 'Synthetic curve' }, { value: 'common', label: 'Common range' }]" /></Field>
                        <Toggle v-model="manualFreq" label="Frequency manual scale" small />
                        <div class="flex gap-2"><NumberInput v-model="fr.min" :min="0.001" unit="Hz" :disabled="!manualFreq" /><NumberInput v-model="fr.max" :min="0.01" unit="Hz" :disabled="!manualFreq" /></div>
                        <Toggle v-model="manualRatio" label="H/V ratio manual scale" small />
                        <div class="flex gap-2"><NumberInput v-model="rr.min" :min="0" :disabled="!manualRatio" /><NumberInput v-model="rr.max" :min="0.1" :disabled="!manualRatio" /></div>
                    </div>
                </Panel>
            </div>
        </div>
        <div class="grid grid-cols-1 gap-4" :class="showProfile ? 'xl:grid-cols-[minmax(0,1fr)_380px]' : ''">
            <Panel :padded="false"><div class="p-2"><ModelPlot :frequency="frequency" :curve="curve" :model="model" :show-experimental="showExp" :show-std="showStd" :show-synthetic="showSyn" :link="link" :freq-range="manualFreq && fr.min && fr.max ? [fr.min, fr.max] : null" :ratio-range="manualRatio && rr.min !== null && rr.max ? [rr.min, rr.max] : null" /></div></Panel>
            <Panel v-if="showProfile" :padded="false">
                <div class="p-2"><ProfilePlot :layers="layers" :marker="model?.vseq?.depth_m ?? null" /></div>
                <div class="px-3 pb-3 text-[12px] text-muted flex flex-wrap gap-x-4 gap-y-1"><span>Vs<sub>30</sub> (offset {{ vs30Offset }} m) = <span class="num text-ui">{{ fmtNum(model?.vs30, 4) }}</span> m/s</span><span>Vs<sub>eq</sub> = <span class="num text-ui">{{ fmtNum(model?.vseq?.value, 4) }}</span> m/s</span></div>
            </Panel>
        </div>
        <Panel title="Saved models" v-if="models.length" :padded="false">
            <ul class="divide-y divide-[var(--ui-border)]">
                <li v-for="m in models" :key="m.id" class="flex items-center gap-3 px-4 py-2 text-[12.5px]"><FolderOpen class="size-4 text-faint" /><span class="font-medium">{{ m.name }}</span><span class="text-faint">{{ m.layers.length }} layers</span><div class="flex-1" /><Button size="xs" @click="loadModel(m.id)">Load</Button><Button size="xs" variant="ghost" @click="deleteModel(m.id)"><Trash2 class="size-3.5" /></Button></li>
            </ul>
        </Panel>
        <p class="text-[12px] text-muted rounded-lg bg-warn-500/10 border border-warn-500/30 px-3 py-2"><strong>Non-uniqueness.</strong> A ground model whose synthetic curve fits the experimental H/V is not unique: different combinations of thickness and velocity produce the same peak frequency (f0 ≈ Vs/4H) and similar shapes. Use independent constraints (boreholes, MASW/ReMi, geology) before drawing conclusions. The synthetic curve is a body-wave transfer-function ratio (Herak 2008), not a full ambient-vibration wavefield simulation.</p>
        <Modal :open="saveOpen" title="Save ground model" @close="saveOpen = false">
            <Field label="Model name"><input v-model="modelName" class="input" autofocus placeholder="e.g. Borehole B1 interpretation" /></Field>
            <template #footer><Button @click="saveOpen = false">Cancel</Button><Button variant="primary" :disabled="!modelName.trim()" @click="saveModel">Save</Button></template>
        </Modal>
    </div>
</template>
