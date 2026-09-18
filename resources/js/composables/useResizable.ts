import { onBeforeUnmount, ref, type Ref } from 'vue';

export interface ResizableOptions {
    min: number;
    max: number;
    initial: number;
    storageKey?: string;
    /** 'left' means the panel is on the left of the splitter (dragging right grows it). */
    side: 'left' | 'right';
}

export function useResizable(opts: ResizableOptions): { size: Ref<number>; dragging: Ref<boolean>; onPointerDown: (e: PointerEvent) => void } {
    let initial = opts.initial;
    if (opts.storageKey) {
        try {
            const v = Number(localStorage.getItem(opts.storageKey));
            if (v >= opts.min && v <= opts.max) initial = v;
        } catch { /* ignore */ }
    }
    const size = ref(initial);
    const dragging = ref(false);
    let startX = 0;
    let startSize = 0;

    function onMove(e: PointerEvent) {
        const dx = e.clientX - startX;
        const next = opts.side === 'left' ? startSize + dx : startSize - dx;
        size.value = Math.min(opts.max, Math.max(opts.min, next));
    }
    function onUp() {
        dragging.value = false;
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        if (opts.storageKey) {
            try { localStorage.setItem(opts.storageKey, String(size.value)); } catch { /* ignore */ }
        }
        window.dispatchEvent(new Event('resize'));
    }
    function onPointerDown(e: PointerEvent) {
        e.preventDefault();
        dragging.value = true;
        startX = e.clientX;
        startSize = size.value;
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
    }
    onBeforeUnmount(onUp);
    return { size, dragging, onPointerDown };
}
