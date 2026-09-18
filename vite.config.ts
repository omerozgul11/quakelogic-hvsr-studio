import { defineConfig } from 'vite';
import laravel from 'laravel-vite-plugin';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
    plugins: [
        laravel({
            input: ['resources/css/app.css', 'resources/js/app.ts'],
            refresh: false,
        }),
        vue(),
        tailwindcss(),
    ],
    resolve: {
        alias: {
            '@': '/resources/js',
        },
    },
    build: {
        chunkSizeWarningLimit: 4000,
        rollupOptions: {
            output: {
                manualChunks(id: string) {
                    if (id.includes('plotly.js')) return 'plotly';
                    return undefined;
                },
            },
        },
    },
    server: {
        host: '127.0.0.1',
    },
});
