// @ts-check
import { defineConfig } from 'astro/config';

// Static site → Cloudflare Pages. No SSR adapter needed: the page is
// pre-rendered and the live data is fetched client-side from api.kingstonpier.ca.
export default defineConfig({
  site: 'https://kingstonpier.ca',
});
