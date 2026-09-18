<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { FolderPlus, FolderOpen, Trash2, Pencil, Activity, ChevronRight, Archive, ArchiveRestore } from 'lucide-vue-next';
import { api } from '@/api';
import type { Project } from '@/api/types';
import { useProjectStore } from '@/stores/project';
import { useToastStore } from '@/stores/toast';
import Button from '@/components/ui/Button.vue';
import Modal from '@/components/ui/Modal.vue';
import Field from '@/components/ui/Field.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';
import PageHeader from '@/components/PageHeader.vue';
import { fmtDate } from '@/utils/format';

const store = useProjectStore();
const toast = useToastStore();
const router = useRouter();
const loading = ref(true);
const error = ref<unknown>(null);

const modal = ref<{ open: boolean; id: string | null; name: string; description: string }>({ open: false, id: null, name: '', description: '' });
const confirmDelete = ref<Project | null>(null);
const saving = ref(false);

async function load() {
    loading.value = true;
    error.value = null;
    try { await store.loadList(); } catch (e) { error.value = e; } finally { loading.value = false; }
}
onMounted(load);

function openCreate() { modal.value = { open: true, id: null, name: '', description: '' }; }
function openRename(p: Project) { modal.value = { open: true, id: p.id, name: p.name, description: p.description ?? '' }; }

async function save() {
    if (!modal.value.name.trim()) return;
    saving.value = true;
    try {
        if (modal.value.id) {
            await api.projects.update(modal.value.id, { name: modal.value.name.trim(), description: modal.value.description });
            toast.success('Project renamed');
        } else {
            const p = await api.projects.create({ name: modal.value.name.trim(), description: modal.value.description });
            toast.success('Project created', p.name);
            modal.value.open = false;
            await open(p.id);
            return;
        }
        modal.value.open = false;
        await load();
    } catch (e) { toast.error('Could not save project', (e as Error).message); } finally { saving.value = false; }
}
async function doDelete() {
    if (!confirmDelete.value) return;
    try {
        await api.projects.remove(confirmDelete.value.id);
        if (store.current?.id === confirmDelete.value.id) store.close();
        toast.success('Project deleted');
        confirmDelete.value = null;
        await load();
    } catch (e) { toast.error('Could not delete project', (e as Error).message); }
}
async function open(id: string) {
    await store.open(id, true);
    await router.push(`/projects/${id}`);
}
const backingUp = ref<string | null>(null);
async function backup(p: Project) {
    backingUp.value = p.id;
    try { await api.projects.backup(p.id); toast.success('Backup downloaded', `${p.name} (zip with all files and database rows)`); }
    catch (e) { toast.error('Backup failed', (e as Error).message); } finally { backingUp.value = null; }
}
const restoreInput = ref<HTMLInputElement | null>(null);
const restoring = ref(false);
async function restore(ev: Event) {
    const f = (ev.target as HTMLInputElement).files?.[0];
    (ev.target as HTMLInputElement).value = '';
    if (!f) return;
    restoring.value = true;
    try { const p = await api.projects.restore(f); toast.success('Project restored', p.name); await load(); }
    catch (e) { toast.error('Restore failed', (e as Error).message); } finally { restoring.value = false; }
}
</script>

<template>
    <div class="p-6 max-w-6xl">
        <PageHeader title="Projects" subtitle="Each project keeps its stations, recordings, processing runs, analyses and exports in its own folder." no-back no-crumbs>
            <template #actions>
                <input ref="restoreInput" type="file" accept=".zip,application/zip" class="hidden" @change="restore" />
                <Button :loading="restoring" title="Recreate a project from a backup zip" @click="restoreInput?.click()"><ArchiveRestore class="size-4" />Restore from backup</Button>
                <Button variant="primary" @click="openCreate"><FolderPlus class="size-4" />New project</Button>
            </template>
        </PageHeader>

        <ErrorBanner v-if="error" :error="error" class="mb-4" @retry="load" />

        <div v-if="loading" class="text-muted text-[12.5px]">Loading projects…</div>
        <EmptyState v-else-if="store.projects.length === 0" title="No projects yet" description="Create a project, then import three-component recordings (TXT, CSV or MiniSEED) to begin an HVSR analysis." :icon="Activity">
            <Button variant="primary" @click="openCreate"><FolderPlus class="size-4" />Create your first project</Button>
        </EmptyState>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <article v-for="p in store.projects" :key="p.id" class="card p-5 flex flex-col gap-3 hover:-translate-y-px hover:shadow-[var(--ui-shadow-lg)] transition cursor-pointer group" :class="store.current?.id === p.id ? 'ring-2 ring-brand-500/40' : ''" @click="open(p.id)">
                <div class="flex items-start gap-3">
                    <span class="grid place-items-center size-10 rounded-xl bg-brand-500/12 text-brand-700 shrink-0 dark:text-brand-300"><FolderOpen class="size-5" /></span>
                    <div class="min-w-0 flex-1">
                        <h2 class="text-[15px] font-semibold truncate leading-tight" :title="p.name">{{ p.name }}</h2>
                        <p class="text-[12px] text-muted line-clamp-2 mt-0.5">{{ p.description || 'No description' }}</p>
                    </div>
                    <div class="flex gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition" @click.stop>
                        <Button icon size="sm" variant="ghost" title="Backup (zip)" :loading="backingUp === p.id" @click="backup(p)"><Archive class="size-3.5" /></Button>
                        <Button icon size="sm" variant="ghost" title="Rename" @click="openRename(p)"><Pencil class="size-3.5" /></Button>
                        <Button icon size="sm" variant="ghost" title="Delete" @click="confirmDelete = p"><Trash2 class="size-3.5" /></Button>
                    </div>
                </div>
                <div class="flex items-center gap-3 mt-auto">
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-[11.5px] text-muted"><span class="num text-ui">{{ p.counts?.stations ?? p.stations_count ?? p.stations?.length ?? 0 }}</span> stations</span>
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-[11.5px] text-muted"><span class="num text-ui">{{ p.counts?.recordings ?? p.recordings_count ?? p.recordings?.length ?? 0 }}</span> recordings</span>
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-[11.5px] text-muted"><span class="num text-ui">{{ p.counts?.analyses ?? p.analyses_count ?? 0 }}</span> analyses</span>
                </div>
                <div class="flex items-center justify-between text-[11px] text-faint">
                    <span>Updated {{ fmtDate(p.updated_at) }}</span>
                    <span class="inline-flex items-center gap-1 font-medium text-brand-700 dark:text-brand-300">Open <ChevronRight class="size-3.5" /></span>
                </div>
            </article>
        </div>
        <p v-if="!loading && store.projects.length" class="mt-5 text-[12px] text-faint">Tip: synthetic example recordings ship in the <span class="num">examples/</span> folder of the installation; import them into any project to try the workflow.</p>

        <Modal :open="modal.open" :title="modal.id ? 'Rename project' : 'New project'" @close="modal.open = false">
            <form class="space-y-3" @submit.prevent="save">
                <Field label="Name"><input v-model="modal.name" class="input" autofocus placeholder="e.g. Site survey 2026" /></Field>
                <Field label="Description" help="Optional."><textarea v-model="modal.description" class="input h-20" /></Field>
            </form>
            <template #footer>
                <Button @click="modal.open = false">Cancel</Button>
                <Button variant="primary" :loading="saving" :disabled="!modal.name.trim()" @click="save">{{ modal.id ? 'Save' : 'Create' }}</Button>
            </template>
        </Modal>

        <Modal :open="!!confirmDelete" title="Delete project?" @close="confirmDelete = null">
            <p class="text-[13px]">This permanently deletes <strong>{{ confirmDelete?.name }}</strong>, its recordings, analyses and exports from disk. This cannot be undone.</p>
            <template #footer>
                <Button @click="confirmDelete = null">Cancel</Button>
                <Button variant="danger" @click="doDelete">Delete project</Button>
            </template>
        </Modal>
    </div>
</template>
