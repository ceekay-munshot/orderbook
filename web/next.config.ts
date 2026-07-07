import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // App-wide Next.js config for the orderbook dashboard goes here.
  // Kept intentionally minimal for the scaffold.
};

export default nextConfig;

// Enables `getCloudflareContext()` (e.g. the D1 binding named `DB`) while
// running `next dev`. Added by the OpenNext Cloudflare adapter. This is a
// no-op outside of local development, so it is safe during `next build`.
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

initOpenNextCloudflareForDev();
