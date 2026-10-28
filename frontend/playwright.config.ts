import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  timeout: 90_000,
  use: { baseURL: process.env.WEB || "http://localhost:5173", channel: process.env.PW_CHANNEL || "chrome", headless: true },
  reporter: "list",
});
