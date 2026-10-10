<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { KeyRound, ShieldCheck, Copy, Check, Upload, Mail, FileText } from 'lucide-vue-next';
import { useLicenseStore } from '@/stores/license';
import { useToastStore } from '@/stores/toast';
import PageHeader from '@/components/PageHeader.vue';
import Panel from '@/components/ui/Panel.vue';
import Button from '@/components/ui/Button.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';

const license = useLicenseStore();
const toast = useToastStore();
const fileInput = ref<HTMLInputElement | null>(null);
const busy = ref(false);
const copied = ref(false);
const importError = ref<string | null>(null);

const st = computed(() => license.status);
const headline = computed(() => st.value?.state === 'licensed' ? 'Licensed' : st.value?.state === 'trial' ? 'Free trial' : 'Licence required');
const detail = computed(() => {
    const s = st.value;
    if (!s) return '';
    if (s.state === 'licensed') return `Licensed to ${s.license?.customer ?? ''}`;
    if (s.state === 'trial') return `${s.trial_info?.days_left ?? 0} of ${s.trial_days} trial days left · exports are marked TRIAL`;
    return s.reason ?? 'The trial has ended.';
});
const tone = computed(() => st.value?.state === 'licensed' ? 'border-ok-500/40 bg-ok-500/8' : st.value?.state === 'trial' ? 'border-warn-500/40 bg-warn-500/10' : 'border-bad-500/40 bg-bad-500/8');

async function importFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    busy.value = true;
    importError.value = null;
    try {
        const result = await license.install(file);
        toast.success(result.state === 'licensed' ? 'Licence activated' : 'Licence file imported', result.message);
    } catch (err) {
        importError.value = (err as Error).message;
    } finally {
        busy.value = false;
    }
}

async function copyMachine() {
    try {
        await navigator.clipboard.writeText(st.value?.machine_id ?? '');
        copied.value = true;
        setTimeout(() => (copied.value = false), 2500);
    } catch {
        toast.warning('Copy is unavailable here', 'Select the Machine ID and copy it manually.');
    }
}

onMounted(() => { license.clearRequired(); void license.load(); });
</script>

<template>
    <div class="p-6 mx-auto max-w-[920px]">
        <PageHeader title="License" subtitle="QuakeLogic HVSR Studio runs as a 14-day trial, then needs a licence file issued for this computer. Licences are verified offline." no-crumbs />

        <ErrorBanner v-if="license.error" :error="new Error(license.error)" title="Licence status unavailable" class="mb-4" />
        <input ref="fileInput" hidden type="file" accept=".qlicense,application/json" @change="importFile" />

        <div v-if="st" class="space-y-4">
            <div class="card p-5 flex items-start gap-4 border" :class="tone">
                <span class="grid place-items-center size-11 rounded-xl shrink-0" :class="st.state === 'licensed' ? 'bg-ok-500/15 text-ok-500' : st.state === 'trial' ? 'bg-warn-500/15 text-warn-500' : 'bg-bad-500/15 text-bad-500'">
                    <ShieldCheck v-if="st.state === 'licensed'" class="size-6" /><KeyRound v-else class="size-6" />
                </span>
                <div class="min-w-0">
                    <h2 class="text-[16px] font-semibold">{{ headline }}</h2>
                    <p class="text-[13px] text-muted mt-0.5">{{ detail }}</p>
                    <p v-if="license.requiredMessage" class="mt-2 text-[12.5px] text-bad-500">{{ license.requiredMessage }}</p>
                    <p v-if="st.license_problem" class="mt-2 text-[12.5px] text-warn-500">{{ st.license_problem }}</p>
                </div>
            </div>

            <Panel v-if="st.license" title="Licence details">
                <dl class="grid grid-cols-[170px_minmax(0,1fr)] gap-x-4 gap-y-2 text-[12.5px]">
                    <dt class="text-muted">Licence</dt><dd class="num">{{ st.license.license_id }} · {{ st.license.edition }}</dd>
                    <dt class="text-muted">Customer</dt><dd>{{ st.license.customer }}</dd>
                    <dt class="text-muted">Computers</dt><dd class="num">{{ st.license.seats }}</dd>
                    <dt class="text-muted">Updates until</dt><dd class="num">{{ st.license.maintenance_until || '—' }}</dd>
                    <dt class="text-muted">Valid until</dt><dd class="num">{{ st.license.expires || 'Perpetual' }}</dd>
                    <dt class="text-muted">This version released</dt><dd class="num">{{ st.release_date }}</dd>
                </dl>
            </Panel>

            <Panel title="Machine ID">
                <div class="flex flex-wrap items-center gap-3">
                    <KeyRound class="size-5 text-muted shrink-0" />
                    <div class="min-w-0">
                        <div class="eyebrow">This computer</div>
                        <div class="num text-[18px] font-semibold tracking-wide select-all">{{ st.machine_id }}</div>
                    </div>
                    <div class="flex-1" />
                    <Button size="sm" @click="copyMachine"><Check v-if="copied" class="size-3.5" /><Copy v-else class="size-3.5" /> {{ copied ? 'Copied' : 'Copy' }}</Button>
                </div>
                <p class="help mt-3">A licence is issued for this computer's Machine ID. Send it to QuakeLogic to buy a licence, then import the .qlicense file you receive. Licences work offline. Projects can always be opened, viewed and saved, even without a licence.</p>
                <p v-if="importError" class="mt-3 text-[12.5px] text-bad-500">{{ importError }}</p>
                <div class="mt-4 flex flex-wrap gap-2">
                    <Button variant="primary" :loading="busy" @click="fileInput?.click()"><Upload class="size-4" /> Import licence file</Button>
                    <a :href="license.mailto" class="inline-flex items-center gap-1.5 rounded-lg border border-ui bg-surface px-3 h-[34px] text-[13px] font-medium hover:bg-surface-2"><Mail class="size-4" /> Request a licence</a>
                    <RouterLink to="/manual?doc=eula" class="inline-flex items-center gap-1.5 rounded-lg px-3 h-[34px] text-[13px] text-muted hover:text-ui"><FileText class="size-4" /> Licence agreement</RouterLink>
                </div>
            </Panel>

            <p class="text-[12px] text-faint">QuakeLogic Inc. · {{ st.sales }} · +1 (916) 899-0391 · Trial period: {{ st.trial_days }} days from first use.</p>
        </div>
        <p v-else-if="license.loading" class="text-[13px] text-muted">Reading licence status…</p>
    </div>
</template>
