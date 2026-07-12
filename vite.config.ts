import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const uiPort = Number(process.env.AIBI_UI_PORT ?? 8686);
const apiPort = Number(process.env.AIBI_API_PORT ?? 8787);

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          return id.replaceAll("\\", "/").endsWith("/src/appNavigationModel.ts") ? "app-navigation" : undefined;
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: uiPort,
    strictPort: true,
    proxy: {
      "/api": `http://127.0.0.1:${apiPort}`
    }
  }
});
