import { inject, onBeforeUnmount, provide, ref, type InjectionKey, type Ref, type Component, watch } from 'vue';

export interface PanelContent {
    title: string;
    component: Component;
    props?: Record<string, unknown>;
}

export interface PanelHost {
    content: Ref<PanelContent | null>;
    collapsed: Ref<boolean>;
    setContent: (c: PanelContent | null) => void;
}

export const PanelKey: InjectionKey<PanelHost> = Symbol('processing-panel');

export function providePanelHost(): PanelHost {
    const content = ref<PanelContent | null>(null);
    const collapsed = ref(false);
    const host: PanelHost = {
        content,
        collapsed,
        setContent: (c) => { content.value = c; },
    };
    provide(PanelKey, host);
    return host;
}

/** Pages call this to place their controls in the right-hand Processing Panel. */
export function useProcessingPanel(content: Ref<PanelContent | null>): PanelHost | undefined {
    const host = inject(PanelKey, undefined);
    if (!host) return undefined;
    watch(content, (c) => host.setContent(c), { immediate: true, deep: false });
    onBeforeUnmount(() => host.setContent(null));
    return host;
}
