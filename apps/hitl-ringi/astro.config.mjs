import react from "@astrojs/react";
import { defineConfig, envField } from "astro/config";

export default defineConfig({
  integrations: [react()],
  envDir: "../..",
  env: {
    schema: {
      PUBLIC_COCO_MATCH_API_BASE_URL: envField.string({
        context: "client",
        access: "public",
        optional: true,
        default: "",
      }),
      PUBLIC_COCOM_API_BASE_URL: envField.string({
        context: "client",
        access: "public",
        optional: true,
        default: "",
      }),
      PUBLIC_COCO_MATCH_API_PREFIX: envField.string({
        context: "client",
        access: "public",
        optional: true,
        default: "/api/v1",
      }),
    },
  },
  output: "static",
});
