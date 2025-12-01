import { defineConfig } from "@solidjs/start/config";

export default defineConfig({
  server: {
    preset: "node-server",
  },
  vite: {
    server: {
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

