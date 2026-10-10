import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/api';
import type { LicenseStatus } from '@/api/types';

export const useLicenseStore = defineStore('license', () => {
    const status = ref<LicenseStatus | null>(null);
    const error = ref<string | null>(null);
    const loading = ref(false);
    const requiredMessage = ref<string | null>(null);   // set when the engine refuses a calculation (HTTP 402)

    const state = computed(() => status.value?.state ?? null);
    const chipLabel = computed(() => {
        if (!status.value) return null;
        if (status.value.state === 'licensed') return 'Licensed';
        return status.value.message;
    });
    const chipTone = computed<'ok' | 'warn' | 'bad' | 'neutral'>(() =>
        status.value?.state === 'licensed' ? 'ok' : status.value?.state === 'trial' ? 'warn' : status.value ? 'bad' : 'neutral');

    async function load() {
        loading.value = true;
        try {
            status.value = await api.license.status();
            error.value = null;
        } catch (e) {
            error.value = (e as Error).message;
        } finally {
            loading.value = false;
        }
    }

    async function install(file: File) {
        status.value = await api.license.install(file);
        requiredMessage.value = null;
        return status.value;
    }

    function markRequired(message: string) { requiredMessage.value = message; void load(); }
    function clearRequired() { requiredMessage.value = null; }

    const mailto = computed(() => {
        const sales = status.value?.sales || 'sales@quakelogic.net';
        const body = `Machine ID: ${status.value?.machine_id ?? ''}\nProduct: QuakeLogic HVSR Studio\nCompany:\nContact person:\nNumber of computers:`;
        return `mailto:${sales}?subject=${encodeURIComponent('HVSR Studio licence request')}&body=${encodeURIComponent(body)}`;
    });

    return { status, error, loading, requiredMessage, state, chipLabel, chipTone, load, install, markRequired, clearRequired, mailto };
});
