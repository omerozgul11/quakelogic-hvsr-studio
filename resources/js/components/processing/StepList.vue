<script setup lang="ts">
import { ref } from 'vue';
import { ArrowUp, ArrowDown, Trash2, Plus, ChevronDown, ChevronRight, RotateCcw } from 'lucide-vue-next';
import Button from '@/components/ui/Button.vue';
import Toggle from '@/components/ui/Toggle.vue';
import Dropdown from '@/components/ui/Dropdown.vue';
import MenuItem from '@/components/ui/MenuItem.vue';
import StepEditor from './StepEditor.vue';
import { STEP_DEFS, describeStep, newStep, stepDef } from './defaults';
import type { Step, StepOp, StepWarning } from '@/api/types';

interface Props { steps: Step[]; fs?: number | null; duration?: number | null; warnings?: StepWarning[]; selectedIndex?: number | null }
const props = defineProps<Props>();
const emit = defineEmits<{ change: []; select: [index: number | null]; reset: [] }>();

const expanded = ref<Set<number>>(new Set());

function add(op: StepOp) {
    props.steps.push(newStep(op));
    expanded.value.add(props.steps.length - 1);
    emit('select', props.steps.length - 1);
    emit('change');
}
function remove(i: number) {
    props.steps.splice(i, 1);
    expanded.value.delete(i);
    emit('select', null);
    emit('change');
}
function move(i: number, d: -1 | 1) {
    const j = i + d;
    if (j < 0 || j >= props.steps.length) return;
    const [s] = props.steps.splice(i, 1);
    props.steps.splice(j, 0, s);
    emit('select', j);
    emit('change');
}
function toggle(i: number) {
    if (expanded.value.has(i)) expanded.value.delete(i);
    else expanded.value.add(i);
    emit('select', i);
}
function warningsFor(i: number): StepWarning[] {
    return (props.warnings ?? []).filter((w) => w.step_index === i);
}
</script>

<template>
    <div class="space-y-2">
        <div class="flex items-center justify-between">
            <h3 class="eyebrow">Processing steps</h3>
            <div class="flex items-center gap-1">
                <Button v-if="steps.length" size="sm" variant="ghost" title="Remove all steps" @click="emit('reset')"><RotateCcw class="size-3.5" />Clear</Button>
                <Dropdown label="Add step" align="right" size="sm" variant="primary">
                    <template #icon><Plus class="size-3.5" /></template>
                    <MenuItem v-for="d in STEP_DEFS" :key="d.op" @click="add(d.op)">{{ d.label }}</MenuItem>
                </Dropdown>
            </div>
        </div>

        <p v-if="steps.length === 0" class="help rounded-lg bg-surface-2 p-3 !mt-2">No processing steps — the raw data is analysed as-is. Add steps with the button above; they are applied in the listed order.</p>

        <ol class="space-y-2">
            <li v-for="(s, i) in steps" :key="i" class="rounded-xl border transition" :class="[selectedIndex === i ? 'border-brand-400 ring-2 ring-brand-500/15' : 'border-ui', s.enabled ? 'bg-surface' : 'bg-surface-2 opacity-70']">
                <div class="flex items-center gap-1.5 pl-2 pr-1.5 h-10">
                    <button class="text-faint hover:text-ui p-0.5 rounded" :title="expanded.has(i) ? 'Hide parameters' : 'Edit parameters'" @click="toggle(i)"><component :is="expanded.has(i) ? ChevronDown : ChevronRight" class="size-3.5" /></button>
                    <span class="grid place-items-center size-5 rounded-full bg-black/6 num text-[10.5px] text-muted dark:bg-white/10">{{ i + 1 }}</span>
                    <button class="flex-1 min-w-0 text-left" @click="toggle(i)">
                        <span class="text-[12.5px] font-medium">{{ stepDef(s.op).label }}</span>
                        <span class="block text-[11px] text-faint truncate">{{ describeStep(s) }}</span>
                    </button>
                    <span v-if="warningsFor(i).length" class="size-2 rounded-full bg-warn-500 shrink-0" :title="warningsFor(i).map((w) => w.message).join('\n')" />
                    <Toggle :model-value="s.enabled" small :help="s.enabled ? 'Enabled — click to skip this step' : 'Disabled — click to apply this step'" @update:model-value="(v) => { s.enabled = v; emit('change'); }" />
                    <button class="text-faint hover:text-ui p-1 rounded disabled:opacity-30" :disabled="i === 0" title="Move up" @click="move(i, -1)"><ArrowUp class="size-3.5" /></button>
                    <button class="text-faint hover:text-ui p-1 rounded disabled:opacity-30" :disabled="i === steps.length - 1" title="Move down" @click="move(i, 1)"><ArrowDown class="size-3.5" /></button>
                    <button class="text-faint hover:text-bad-500 p-1 rounded" title="Remove step" @click="remove(i)"><Trash2 class="size-3.5" /></button>
                </div>
                <div v-if="expanded.has(i)" class="px-3 pb-3 pt-2 mx-2 mb-1 rounded-lg bg-surface-2/70">
                    <StepEditor :step="s" :fs="fs" :duration="duration" @change="emit('change')" />
                    <ul v-if="warningsFor(i).length" class="mt-2 space-y-1">
                        <li v-for="(w, k) in warningsFor(i)" :key="k" class="text-[11.5px] text-warn-500">{{ w.message }}</li>
                    </ul>
                </div>
            </li>
        </ol>
    </div>
</template>
