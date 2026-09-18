<script setup lang="ts">
import { computed } from 'vue';
import { Loader2 } from 'lucide-vue-next';

interface Props {
    variant?: 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger' | 'link';
    size?: 'xs' | 'sm' | 'md' | 'lg';
    loading?: boolean;
    disabled?: boolean;
    type?: 'button' | 'submit';
    title?: string;
    /** Square icon-only button. */
    icon?: boolean;
}
const props = withDefaults(defineProps<Props>(), { variant: 'secondary', size: 'md', loading: false, disabled: false, type: 'button', icon: false });

const cls = computed(() => {
    const base = 'inline-flex items-center justify-center gap-1.5 font-medium transition select-none whitespace-nowrap disabled:opacity-45 disabled:cursor-not-allowed active:scale-[0.985]';
    const sizes: Record<string, string> = {
        xs: props.icon ? 'size-6 rounded-md text-[12px]' : 'h-6 px-2 rounded-md text-[11.5px]',
        sm: props.icon ? 'size-7 rounded-lg text-[12px]' : 'h-7 px-2.5 rounded-lg text-[12px]',
        md: props.icon ? 'size-[34px] rounded-lg text-[13px]' : 'h-[34px] px-3.5 rounded-lg text-[13px]',
        lg: props.icon ? 'size-10 rounded-xl text-[14px]' : 'h-10 px-5 rounded-xl text-[14px]',
    };
    const v: Record<string, string> = {
        primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-[0_1px_2px_rgba(0,0,0,0.12)] dark:bg-brand-400 dark:text-brand-900 dark:hover:bg-brand-300',
        accent: 'bg-accent-600 text-white hover:bg-accent-700 dark:bg-accent-200 dark:text-accent-900',
        secondary: 'bg-surface text-ui border border-ui-strong hover:bg-surface-2 shadow-[0_1px_1px_rgba(0,0,0,0.03)]',
        ghost: 'text-muted hover:bg-surface-2 hover:text-ui',
        danger: 'bg-bad-500 text-white hover:bg-red-700',
        link: 'text-brand-700 hover:underline px-0 dark:text-brand-300',
    };
    return `${base} ${sizes[props.size]} ${v[props.variant]}`;
});
</script>

<template>
    <button :type="type" :class="cls" :disabled="disabled || loading" :title="title">
        <Loader2 v-if="loading" class="size-3.5 animate-spin" />
        <slot />
    </button>
</template>
