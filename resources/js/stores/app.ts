import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import { api } from '@/api';
import type { AppStatus, Settings } from '@/api/types';
import type { UnitSystem } from '@/utils/units';

export type ThemePref = 'light' | 'dark' | 'system';
const THEME_KEY = 'hvsr-theme';
const UNITS_KEY = 'hvsr-units';

function readUnits(): UnitSystem {
    try { return localStorage.getItem(UNITS_KEY) === 'us' ? 'us' : 'metric'; } catch { return 'metric'; }
}

function readTheme(): ThemePref {
    try {
        const v = localStorage.getItem(THEME_KEY);
        if (v === 'light' || v === 'dark' || v === 'system') return v;
    } catch { /* ignore */ }
    return 'system';
}

export const useAppStore = defineStore('app', () => {
    const theme = ref<ThemePref>(readTheme());
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const systemDark = ref(media.matches);
    media.addEventListener('change', (e) => (systemDark.value = e.matches));
    const isDark = computed(() => theme.value === 'dark' || (theme.value === 'system' && systemDark.value));

    function applyTheme() {
        document.documentElement.classList.toggle('dark', isDark.value);
    }
    watch(isDark, applyTheme, { immediate: true });

    function setTheme(t: ThemePref) {
        theme.value = t;
        try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
    }

    const status = ref<AppStatus | null>(null);
    const statusError = ref<string | null>(null);
    const settings = ref<Settings | null>(null);
    let timer: number | null = null;

    const engineOk = computed(() => status.value?.engine?.status === 'ok');
    const engineLabel = computed(() => {
        if (statusError.value) return 'Server unreachable';
        if (!status.value) return 'Checking…';
        return engineOk.value ? 'Engine ready' : 'Engine offline';
    });

    let failures = 0;
    async function refreshStatus() {
        try {
            status.value = await api.app.status();
            statusError.value = null;
            failures = 0;
        } catch (e) {
            // One slow or failed poll (e.g. during a large upload) is not an outage.
            failures += 1;
            if (failures >= 2) statusError.value = (e as Error).message;
        }
    }
    function startPolling(intervalMs = 15000) {
        void refreshStatus();
        if (timer !== null) window.clearInterval(timer);
        timer = window.setInterval(() => void refreshStatus(), intervalMs);
    }
    const unitSystem = ref<UnitSystem>(readUnits());
    function applyUnitsFromSettings() {
        const u = settings.value?.unit_system;
        if (u === 'us' || u === 'metric') {
            unitSystem.value = u;
            try { localStorage.setItem(UNITS_KEY, u); } catch { /* ignore */ }
        }
    }
    async function loadSettings() {
        try { settings.value = await api.app.settings(); applyUnitsFromSettings(); } catch { settings.value = null; }
    }
    async function saveSettings(patch: Partial<Settings>) {
        settings.value = await api.app.saveSettings(patch);
        applyUnitsFromSettings();
    }
    /** Switch the display unit system (stored on the server and mirrored locally for instant load). */
    async function setUnitSystem(u: UnitSystem) {
        unitSystem.value = u;
        try { localStorage.setItem(UNITS_KEY, u); } catch { /* ignore */ }
        try { await saveSettings({ unit_system: u }); } catch { /* keep the local choice */ }
    }

    return { theme, isDark, setTheme, status, statusError, engineOk, engineLabel, refreshStatus, startPolling, settings, loadSettings, saveSettings, unitSystem, setUnitSystem };
});
