import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// OpenNext -> Cloudflare Workers build configuration.
// Defaults are fine for the scaffold; incremental cache / queue / tag cache
// options can be added here in later steps if we need ISR or on-demand
// revalidation. See https://opennext.js.org/cloudflare/config
export default defineCloudflareConfig();
