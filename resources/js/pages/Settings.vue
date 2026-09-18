<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { useAppStore } from '@/stores/app';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import { useGuideStore } from '@/stores/guide';
import Panel from '@/components/ui/Panel.vue';
import PageHeader from '@/components/PageHeader.vue';
import Select from '@/components/ui/Select.vue';
import Button from '@/components/ui/Button.vue';
import Badge from '@/components/ui/Badge.vue';
import Tabs from '@/components/ui/Tabs.vue';
import { UNIT_SYSTEMS, type UnitSystem } from '@/utils/units';

const app = useAppStore();
const project = useProjectStore();
const toast = useToastStore();
const guide = useGuideStore();
const saving = ref(false);
const defaultPreset = ref<string | null>(null);

onMounted(async () => {
    await app.loadSettings();
    await app.refreshStatus();
    defaultPreset.value = (app.settings?.default_preset_id as string | null) ?? null;
});

const presetOptions = computed(() => [{ value: null, label: 'None' }, ...project.presets.map((p) => ({ value: p.id, label: p.name }))]);
const engine = computed(() => app.status?.engine ?? null);

async function save() {
    saving.value = true;
    try {
        await app.saveSettings({ theme_default: app.theme, default_preset_id: defaultPreset.value });
        toast.success('Settings saved');
    } catch (e) { toast.error('Could not save settings', (e as Error).message); } finally { saving.value = false; }
}
</script>

<template>
    <div class="p-6 mx-auto max-w-[1100px]">
        <PageHeader title="Settings" subtitle="Preferences are stored in this browser; the data directory and engine address come from the launcher configuration." no-crumbs />

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
            <div class="space-y-4">
                <Panel title="Appearance">
                    <div class="grid grid-cols-[170px_minmax(0,1fr)] items-center gap-x-4 gap-y-3 text-[12.5px]">
                        <label class="text-muted">Theme</label>
                        <Select :model-value="app.theme" :options="[{ value: 'system', label: 'Follow system' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]" @update:model-value="app.setTheme($event as 'light' | 'dark' | 'system')" />
                    </div>
                    <p class="help mt-3">Light, dark, or the operating-system setting. Plots switch with the theme.</p>
                </Panel>

                <Panel title="Units">
                    <div class="grid grid-cols-[170px_minmax(0,1fr)] items-center gap-x-4 gap-y-3 text-[12.5px]">
                        <label class="text-muted">Unit system</label>
                        <Tabs :model-value="app.unitSystem" :tabs="UNIT_SYSTEMS.map((u) => ({ key: u.value, label: u.label }))" small @update:model-value="app.setUnitSystem($event as UnitSystem)" />
                    </div>
                    <p class="help mt-3">Changes how elevations (m / ft) and physical amplitudes and spectra (m/s → in/s, m/s² → in/s², m → in) are displayed. Frequencies stay in Hz, raw counts stay counts, and CSV/JSON exports always keep the original SI or raw units.</p>
                </Panel>

                <Panel title="Defaults">
                    <div class="grid grid-cols-[170px_minmax(0,1fr)] items-center gap-x-4 gap-y-3 text-[12.5px]">
                        <label class="text-muted">Default processing preset</label>
                        <Select v-model="defaultPreset" :options="presetOptions" />
                    </div>
                    <p class="help mt-3">{{ project.current ? `Presets of project “${project.current.name}”. The preset is pre-selected in the batch runner and the toolbox.` : 'Open a project to choose one of its presets.' }}</p>
                    <div class="mt-4 flex justify-end"><Button variant="primary" :loading="saving" @click="save">Save</Button></div>
                </Panel>

                <Panel title="Application">
                    <dl class="grid grid-cols-[170px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[12.5px]">
                        <dt class="text-muted">Version</dt><dd class="num">{{ app.status?.app_version ?? '—' }}</dd>
                        <dt class="text-muted">Data directory</dt><dd class="num break-all">{{ app.status?.data_dir ?? '—' }}</dd>
                        <dt class="text-muted">Documentation</dt><dd class="space-x-2"><RouterLink to="/manual" class="underline">User manual</RouterLink><span class="text-faint">·</span><RouterLink to="/manual?doc=hvsr-algorithms" class="underline">HVSR algorithms</RouterLink><span class="text-faint">·</span><RouterLink to="/manual?doc=validation" class="underline">Validation</RouterLink></dd>
                        <dt class="text-muted">Licences</dt><dd><RouterLink to="/manual?doc=notices" class="underline">Third-party notices</RouterLink></dd>
                        <dt class="text-muted">Privacy</dt><dd>Runs fully offline on this computer. No account, no activation, no network connection.</dd>
                    </dl>
                </Panel>
            </div>

            <div class="space-y-4">
                <Panel title="Processing engine">
                    <template #actions><Button size="sm" @click="app.refreshStatus()">Check now</Button></template>
                    <dl class="grid grid-cols-[170px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[12.5px]">
                        <dt class="text-muted">Status</dt><dd><Badge :tone="app.engineOk ? 'ok' : 'bad'">{{ app.engineLabel }}</Badge> <span v-if="engine?.message" class="text-muted ml-2">{{ engine.message }}</span></dd>
                        <dt class="text-muted">Engine URL</dt><dd class="num break-all">{{ app.settings?.engine_url ?? '—' }}</dd>
                        <dt class="text-muted">Engine version</dt><dd class="num">{{ engine?.engine_version ?? '—' }}</dd>
                        <dt class="text-muted">Python</dt><dd class="num">{{ engine?.python ?? '—' }}</dd>
                        <dt class="text-muted">Workers / running</dt><dd class="num">{{ engine?.workers ?? '—' }} / {{ engine?.jobs_running ?? '—' }}</dd>
                        <dt class="text-muted">Libraries</dt>
                        <dd class="flex flex-wrap gap-1.5">
                            <span v-for="(v, k) in engine?.versions ?? {}" :key="k" class="inline-flex items-center gap-1 rounded-md border border-ui bg-surface-2 px-2 py-0.5 text-[11.5px]"><span class="text-muted">{{ k }}</span><span class="num">{{ v }}</span></span>
                            <span v-if="!engine" class="text-faint">—</span>
                        </dd>
                    </dl>
                    <p v-if="!app.engineOk" class="help mt-3">The engine is started by the launcher (<span class="num">HVSR Studio.bat</span> / <span class="num">hvsr-studio.sh</span>). If it is not running, close the app and start it again from the launcher.</p>
                </Panel>

                <Panel title="Help">
                    <p class="text-[12.5px] text-muted">The <RouterLink to="/manual" class="underline text-ui">User manual</RouterLink> section holds the complete documentation, and the <strong>?</strong> button in the top bar opens the step-by-step guided workflow.</p>
                    <div class="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" @click="guide.show(0)">Open the guided workflow</Button>
                        <Button size="sm" @click="guide.dismiss(false)" :disabled="!guide.dismissed">Show it automatically again</Button>
                    </div>
                </Panel>
            </div>
        </div>
    </div>
</template>
