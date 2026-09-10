import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  server: {
    watch: {
      // Research archives do not need module watching. Keep public exports
      // watched: Vite uses add/unlink events to update its static-file index.
      // GLB/PNG changes have no module importers and do not reload the game.
      ignored: ["**/.tooling/**", "**/references/**", "**/assets/**", "**/backups/**", "**/docs/**"],
    },
  },
  build: {
    // Explicit local code-only rebuilds can retain an already verified asset
    // snapshot. Normal builds always copy the complete current public assets.
    copyPublicDir: process.env.DEPLOY_RELEASE !== "1" && process.env.STREET_CODE_ONLY !== "1",
    emptyOutDir: process.env.DEPLOY_RELEASE === "1" || process.env.STREET_CODE_ONLY !== "1",
    rollupOptions: {
      input: {
        game: fileURLToPath(new URL("./index.html", import.meta.url)),
        streets: fileURLToPath(new URL("./streets-review.html", import.meta.url)),
        ...(process.env.DEPLOY_RELEASE === "1" ? {} : { architecture: fileURLToPath(new URL("./architecture-review.html", import.meta.url)) }),
      },
    },
  },
});
