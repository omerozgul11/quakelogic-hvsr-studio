<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import { X } from 'lucide-vue-next';
import { api } from '@/api';
import type { Recording, Survey, Ulid } from '@/api/types';
import { useToastStore } from '@/stores/toast';
import { useUnits } from '@/composables/useUnits';
import Modal from '@/components/ui/Modal.vue';
import Button from '@/components/ui/Button.vue';
import Field from '@/components/ui/Field.vue';
import NumberInput from '@/components/ui/NumberInput.vue';
import { fmtDuration, fmtHz, fmtUtc } from '@/utils/format';

/** QLExplorer-style "Report generation" dialog: survey and place details, two photos, notes. */
interface Props { open: boolean; analysisId: Ulid; recording: Recording | null; survey: Survey | null; generating?: boolean }
const props = withDefaults(defineProps<Props>(), { generating: false });
const emit = defineEmits<{ close: []; saved: [survey: Survey]; generate: [] }>();
const toast = useToastStore();
const units = useUnits();

const form = reactive<Survey>({ date: null, client: '', place_id: '', address: '', latitude: null, longitude: null, datum: 'WGS84', elevation_m: null, weather: '', notes: '', photos: [] });
const elevationDisplay = ref<number | null>(null);
const photos = reactive<{ file: File | null; preview: string | null; remove: boolean }[]>([{ file: null, preview: null, remove: false }, { file: null, preview: null, remove: false }]);
const saving = ref(false);

watch(() => [props.open, props.survey] as const, () => {
    if (!props.open) return;
    const s = props.survey ?? {};
    Object.assign(form, { date: s.date ?? new Date().toISOString().slice(0, 10), client: s.client ?? '', place_id: s.place_id ?? props.recording?.station?.code ?? '', address: s.address ?? '', latitude: s.latitude ?? props.recording?.station?.latitude ?? null, longitude: s.longitude ?? props.recording?.station?.longitude ?? null, datum: s.datum ?? 'WGS84', elevation_m: s.elevation_m ?? props.recording?.station?.elevation ?? null, weather: s.weather ?? '', notes: s.notes ?? '', photos: s.photos ?? [] });
    elevationDisplay.value = units.lengthToDisplay(form.elevation_m);
    photos.forEach((p, i) => { p.file = null; p.remove = false; p.preview = s.photos?.[i]?.url ?? null; });
}, { immediate: true });

function pick(i: number, ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (!f) return;
    photos[i].file = f;
    photos[i].remove = false;
    photos[i].preview = URL.createObjectURL(f);
}
function clearPhoto(i: number) { photos[i].file = null; photos[i].preview = null; photos[i].remove = true; }

async function save(): Promise<Survey | null> {
    saving.value = true;
    try {
        const fd = new FormData();
        const elev = units.lengthFromDisplay(elevationDisplay.value);
        const fields: Record<string, string | number | null | undefined> = { date: form.date, client: form.client, place_id: form.place_id, address: form.address, latitude: form.latitude, longitude: form.longitude, datum: form.datum, elevation_m: elev, weather: form.weather, notes: form.notes };
        for (const [k, v] of Object.entries(fields)) if (v !== null && v !== undefined) fd.append(k, String(v));
        photos.forEach((p, i) => { if (p.file) fd.append(`photo${i + 1}`, p.file, p.file.name); if (p.remove) fd.append(`remove_photo${i + 1}`, '1'); });
        const s = await api.analyses.saveSurvey(props.analysisId, fd);
        emit('saved', s);
        return s;
    } catch (e) { toast.error('Could not save the report details', (e as Error).message); return null; } finally { saving.value = false; }
}
async function saveAndGenerate() { if (await save()) emit('generate'); }
</script>

<template>
    <Modal :open="open" title="Report details" width="max-w-3xl" @close="emit('close')">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-3">
            <section class="space-y-2.5">
                <h3 class="eyebrow">Survey</h3>
                <Field label="Date"><input v-model="form.date" type="date" class="input" /></Field>
                <Field label="Client"><input v-model="form.client" class="input" /></Field>
                <h3 class="eyebrow pt-2">Place</h3>
                <Field label="Place ID"><input v-model="form.place_id" class="input" /></Field>
                <Field label="Address"><input v-model="form.address" class="input" /></Field>
                <div class="grid grid-cols-2 gap-2">
                    <Field label="Latitude"><NumberInput :model-value="form.latitude ?? null" :min="-90" :max="90" unit="°" nullable @update:model-value="form.latitude = $event" /></Field>
                    <Field label="Longitude"><NumberInput :model-value="form.longitude ?? null" :min="-180" :max="180" unit="°" nullable @update:model-value="form.longitude = $event" /></Field>
                    <Field label="Datum"><input v-model="form.datum" class="input" /></Field>
                    <Field :label="`Elevation (${units.lengthLabel.value})`"><NumberInput v-model="elevationDisplay" nullable /></Field>
                </div>
                <Field label="Weather"><input v-model="form.weather" class="input" placeholder="e.g. clear, light wind" /></Field>
            </section>
            <section class="space-y-2.5">
                <h3 class="eyebrow">Photos</h3>
                <div class="grid grid-cols-2 gap-2">
                    <div v-for="(p, i) in photos" :key="i" class="rounded-lg border border-ui p-2 space-y-1.5">
                        <div class="aspect-[4/3] rounded-md bg-surface-2 grid place-items-center overflow-hidden"><img v-if="p.preview" :src="p.preview" class="object-cover w-full h-full" alt="" /><span v-else class="text-faint text-[11px]">Photo {{ i + 1 }}</span></div>
                        <div class="flex items-center gap-1">
                            <label class="flex-1"><input type="file" accept="image/png,image/jpeg" class="hidden" @change="pick(i, $event)" /><span class="inline-flex w-full justify-center rounded-md border border-ui px-2 py-1 text-[11.5px] cursor-pointer hover:bg-surface-2">Browse…</span></label>
                            <button v-if="p.preview" class="text-faint hover:text-bad-500" title="Remove" @click="clearPhoto(i)"><X class="size-3.5" /></button>
                        </div>
                    </div>
                </div>
                <Field label="Notes"><textarea v-model="form.notes" class="input h-24" /></Field>
                <h3 class="eyebrow pt-2">Signal</h3>
                <dl class="grid grid-cols-[110px_1fr] gap-y-1 text-[12px]">
                    <dt class="text-muted">Unit</dt><dd class="num">{{ recording?.units ?? 'counts' }}</dd>
                    <dt class="text-muted">Length</dt><dd class="num">{{ fmtDuration(recording?.duration_s) }}</dd>
                    <dt class="text-muted">Start time</dt><dd class="num">{{ fmtUtc(recording?.start_time) }}</dd>
                    <dt class="text-muted">Sampling frequency</dt><dd class="num">{{ fmtHz(recording?.sample_rate) }}</dd>
                </dl>
            </section>
        </div>
        <template #footer>
            <Button @click="emit('close')">Cancel</Button>
            <Button :loading="saving" @click="save">Save details</Button>
            <Button variant="primary" :loading="saving || generating" @click="saveAndGenerate">Generate report</Button>
        </template>
    </Modal>
</template>
