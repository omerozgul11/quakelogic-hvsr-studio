import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { router } from './router';
import { useAppStore } from './stores/app';

const app = createApp(App);
app.use(createPinia());
app.use(router);

const appStore = useAppStore();
appStore.startPolling(15000);

// Presence heartbeat: the launcher keeps the services alive while at least one window is open
// and shuts them down a few seconds after the last window closes.
const heartbeat = () => { void fetch('/api/app/heartbeat', { method: 'POST', keepalive: true, headers: { Accept: 'application/json' } }).catch(() => undefined); };
heartbeat();
window.setInterval(heartbeat, 4000);
window.addEventListener('pagehide', () => { try { navigator.sendBeacon('/api/app/goodbye'); } catch { /* ignore */ } });
void appStore.loadSettings();

app.mount('#app');
