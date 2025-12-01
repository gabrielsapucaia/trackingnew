import { defineConfig } from "@solidjs/start/config";

export default defineConfig({
  server: {
    preset: "node-server",
  },
  vite: {
    server: {
      proxy: {
        // Proxy API requests to backend
        '/api': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
        '/stats': {
          target: 'http://localhost:8080',
          changeOrigin: true,
        },
      },
      headers: {
        // Required for SharedArrayBuffer support
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
      },
    },
    resolve: {
      alias: {
        "~": "/src",
      },
    },
  },
});



