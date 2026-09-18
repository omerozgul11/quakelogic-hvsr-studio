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
void appStore.loadSettings();

app.mount('#app');
