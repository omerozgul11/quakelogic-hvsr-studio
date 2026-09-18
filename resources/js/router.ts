import { createRouter, createWebHistory } from 'vue-router';

export const router = createRouter({
    history: createWebHistory('/'),
    routes: [
        { path: '/', redirect: '/projects' },
        { path: '/projects', name: 'projects', component: () => import('./pages/Projects.vue'), meta: { section: 'projects', title: 'Projects' } },
        { path: '/projects/:p', name: 'project', component: () => import('./pages/ProjectOverview.vue'), meta: { section: 'projects', title: 'Project overview' } },
        { path: '/projects/:p/import', name: 'import', component: () => import('./pages/ImportWizard.vue'), meta: { section: 'import', title: 'Import & validation' } },
        { path: '/projects/:p/compare', name: 'compare', component: () => import('./pages/BatchCompare.vue'), meta: { section: 'compare', title: 'Batch comparison' } },
        { path: '/projects/:p/reports', name: 'reports', component: () => import('./pages/Reports.vue'), meta: { section: 'reports', title: 'Reports & exports' } },
        { path: '/recordings/:r/waveforms', name: 'waveforms', component: () => import('./pages/Waveforms.vue'), meta: { section: 'waveforms', title: 'Waveforms & preprocessing' } },
        { path: '/recordings/:r/windows', name: 'windows', component: () => import('./pages/WindowSelection.vue'), meta: { section: 'windows', title: 'Window selection' } },
        { path: '/recordings/:r/hvsr', name: 'hvsr-new', component: () => import('./pages/HvsrAnalysis.vue'), meta: { section: 'hvsr', title: 'HVSR analysis' } },
        { path: '/analyses/:a', name: 'analysis', component: () => import('./pages/HvsrAnalysis.vue'), meta: { section: 'hvsr', title: 'HVSR analysis' } },
        { path: '/manual', name: 'manual', component: () => import('./pages/Manual.vue'), meta: { section: 'manual', title: 'User manual' } },
        { path: '/settings', name: 'settings', component: () => import('./pages/Settings.vue'), meta: { section: 'settings', title: 'Settings' } },
        { path: '/:pathMatch(.*)*', redirect: '/projects' },
    ],
});

router.afterEach((to) => {
    const t = (to.meta.title as string | undefined) ?? '';
    document.title = t ? `${t} · QuakeLogic HVSR Studio` : 'QuakeLogic HVSR Studio';
});
