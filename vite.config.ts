import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
const target = process.env.WEBUI_BACKEND_URL || 'http://127.0.0.1:8080';
export default defineConfig({
	plugins: [sveltekit()],
	build: { target: 'es2022' },
	server: {
		// Explicit domain for access through the existing HTTPS proxy/tunnel.
		allowedHosts: ['eurse.me', 'chat.eurse.me'],
		proxy: {
			'/api': { target, changeOrigin: true },
			'/oauth': { target, changeOrigin: true },
			'/ws': { target, changeOrigin: true, ws: true }
		}
	}
});
