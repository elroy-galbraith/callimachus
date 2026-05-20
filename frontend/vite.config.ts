import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward /api/* to the FastAPI dev server. Same-origin from the
      // browser's perspective, so CORS is moot in dev.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
    },
  },
});
