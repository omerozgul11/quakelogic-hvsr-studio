import { defineStore } from 'pinia';
import { ref } from 'vue';

export interface Toast {
    id: number;
    kind: 'info' | 'success' | 'warning' | 'error';
    title: string;
    message?: string;
    timeout: number;
}

let seq = 1;

export const useToastStore = defineStore('toast', () => {
    const toasts = ref<Toast[]>([]);

    function push(kind: Toast['kind'], title: string, message?: string, timeout = kind === 'error' ? 9000 : 4500) {
        const id = seq++;
        toasts.value.push({ id, kind, title, message, timeout });
        if (timeout > 0) setTimeout(() => dismiss(id), timeout);
        return id;
    }
    function dismiss(id: number) {
        toasts.value = toasts.value.filter((t) => t.id !== id);
    }
    return {
        toasts,
        dismiss,
        info: (t: string, m?: string) => push('info', t, m),
        success: (t: string, m?: string) => push('success', t, m),
        warning: (t: string, m?: string) => push('warning', t, m),
        error: (t: string, m?: string) => push('error', t, m),
    };
});
