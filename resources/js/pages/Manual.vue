<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { marked, type Tokens } from 'marked';
import { BookOpen, Search, Check, Compass } from 'lucide-vue-next';
import { useGuideStore } from '@/stores/guide';
import Button from '@/components/ui/Button.vue';
import { api } from '@/api';
import type { DocInfo } from '@/api/types';
import EmptyState from '@/components/ui/EmptyState.vue';
import ErrorBanner from '@/components/ui/ErrorBanner.vue';

interface TocEntry { id: string; text: string; depth: number }

const route = useRoute();
const router = useRouter();
const guide = useGuideStore();
const docs = ref<DocInfo[]>([]);
const current = ref<string>((route.query.doc as string) || 'user-guide');
const html = ref('');
const toc = ref<TocEntry[]>([]);
const loading = ref(true);
const error = ref<unknown>(null);
const query = ref('');
const content = ref<HTMLElement | null>(null);

function slugify(text: string): string {
    return text.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-').slice(0, 80);
}

function render(markdown: string): { html: string; toc: TocEntry[] } {
    const entries: TocEntry[] = [];
    const used = new Set<string>();
    const renderer = new marked.Renderer();
    renderer.heading = function ({ tokens, depth }: Tokens.Heading) {
        const text = this.parser.parseInline(tokens);
        let id = slugify(text) || `section-${entries.length + 1}`;
        while (used.has(id)) id += '-';
        used.add(id);
        if (depth <= 3) entries.push({ id, text: text.replace(/<[^>]+>/g, ''), depth });
        return `<h${depth} id="${id}">${text}</h${depth}>`;
    };
    renderer.link = function ({ href, title, tokens }: Tokens.Link) {
        const text = this.parser.parseInline(tokens);
        const t = title ? ` title="${title}"` : '';
        if (href.startsWith('http://') || href.startsWith('https://')) return `<a href="${href}"${t} target="_blank" rel="noopener">${text}</a>`;
        if (href.startsWith('#')) return `<a href="${href}"${t} data-anchor>${text}</a>`;
        return `<span class="text-muted"${t}>${text}</span><code class="text-[11px]">${href}</code>`;
    };
    const out = marked.parse(markdown, { gfm: true, renderer, async: false }) as string;
    return { html: out, toc: entries };
}

async function load(doc: string) {
    loading.value = true;
    error.value = null;
    try {
        const md = await api.docs.get(doc);
        const rendered = render(md);
        html.value = rendered.html;
        toc.value = rendered.toc;
        await nextTick();
        if (route.hash) jump(route.hash.slice(1));
        else content.value?.closest('main')?.scrollTo({ top: 0 });
    } catch (e) {
        error.value = e;
        html.value = '';
        toc.value = [];
    } finally {
        loading.value = false;
    }
}

function jump(id: string) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function onContentClick(ev: MouseEvent) {
    const a = (ev.target as HTMLElement).closest('a[data-anchor]') as HTMLAnchorElement | null;
    if (a) { ev.preventDefault(); jump(decodeURIComponent(a.getAttribute('href')!.slice(1))); }
}

const filteredToc = computed(() => {
    const q = query.value.trim().toLowerCase();
    return q ? toc.value.filter((t) => t.text.toLowerCase().includes(q)) : toc.value;
});

watch(current, (doc) => { router.replace({ query: { doc } }); load(doc); });

onMounted(async () => {
    try { docs.value = await api.docs.list(); } catch { docs.value = [{ key: 'user-guide', title: 'User guide', available: true }]; }
    await load(current.value);
});
</script>

<template>
    <div class="p-6 max-w-[1400px]">
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
                <h1 class="page-title flex items-center gap-2"><BookOpen class="size-5 text-brand-600" /> User manual</h1>
                <p class="text-[12.5px] text-muted mt-0.5">The complete documentation is bundled with the application and works offline. The same text ships as Markdown in the <code>docs/</code> folder.</p>
            </div>
            <div class="segmented">
                <button v-for="d in docs" :key="d.key" class="seg-btn" :class="{ active: current === d.key }" :disabled="!d.available" :title="d.available ? '' : 'Not included in this installation'" @click="current = d.key">{{ d.title }}</button>
            </div>
        </div>

        <section class="card p-5 mb-5">
            <div class="flex flex-wrap items-center gap-3 mb-3">
                <h2 class="text-[14px] font-semibold flex items-center gap-2"><Compass class="size-4 text-brand-600" /> Guided workflow</h2>
                <span class="text-[12px] text-muted">{{ guide.completed }} of {{ guide.steps.length }} steps done in {{ guide.steps[0]?.done ? 'the open project' : 'this session' }}. Follow the steps in order; each one opens the right page.</span>
                <div class="flex-1" />
                <Button variant="primary" size="sm" @click="guide.show(guide.nextIncomplete >= 0 ? guide.nextIncomplete : 0)"><Compass class="size-3.5" /> Start the step-by-step guide</Button>
            </div>
            <ol class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
                <li v-for="(s, i) in guide.steps" :key="s.key" class="rounded-lg border border-ui p-3 flex gap-2.5" :class="s.done ? 'bg-ok-500/5' : ''">
                    <span class="mt-0.5 grid place-items-center size-5 rounded-full shrink-0 text-[10.5px] font-medium" :class="s.done ? 'bg-ok-500/15 text-ok-500' : 'bg-surface-2 text-muted'"><Check v-if="s.done" class="size-3" /><template v-else>{{ i + 1 }}</template></span>
                    <div class="min-w-0">
                        <div class="text-[12.5px] font-medium leading-tight">{{ s.title }} <span v-if="s.optional" class="text-[10.5px] font-normal text-faint">optional</span></div>
                        <p class="text-[11.5px] text-muted mt-1 line-clamp-2">{{ s.summary }}</p>
                        <div class="mt-1.5 flex gap-2">
                            <button class="text-[11.5px] underline text-brand-600 disabled:no-underline disabled:text-faint" :disabled="!s.route" :title="s.blocked ?? ''" @click="s.route && router.push(s.route)">Open</button>
                            <button class="text-[11.5px] underline text-muted" @click="guide.show(i)">Details</button>
                            <button class="text-[11.5px] underline text-muted" @click="current = 'user-guide'; jump(s.docAnchor)">Manual</button>
                        </div>
                    </div>
                </li>
            </ol>
        </section>

        <ErrorBanner v-if="error" :error="error" class="mb-4" />

        <div class="grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-5">
            <aside class="lg:sticky lg:top-3 self-start card p-3 max-h-[calc(100vh-140px)] overflow-auto scroll-thin">
                <div class="relative mb-2">
                    <Search class="size-3.5 absolute left-2 top-2.5 text-faint" />
                    <input v-model="query" type="search" placeholder="Find a section" class="w-full rounded-md border border-ui bg-surface pl-7 pr-2 py-1.5 text-[12px]" />
                </div>
                <EmptyState v-if="!loading && !filteredToc.length" title="No sections" description="Nothing matches your search." compact />
                <nav v-else class="space-y-0.5">
                    <button v-for="t in filteredToc" :key="t.id" class="block w-full text-left rounded px-2 py-1 text-[12px] text-muted hover:text-ui hover:bg-brand-600/5 truncate" :class="{ 'pl-5': t.depth === 3, 'font-medium text-ui': t.depth === 1 }" :title="t.text" @click="jump(t.id)">{{ t.text }}</button>
                </nav>
            </aside>

            <article ref="content" class="card px-8 py-6 markdown" @click="onContentClick">
                <p v-if="loading" class="text-muted text-[13px]">Loading…</p>
                <div v-else v-html="html" />
            </article>
        </div>
    </div>
</template>
