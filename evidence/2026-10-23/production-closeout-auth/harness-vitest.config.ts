import {defineConfig} from 'vitest/config';
export default defineConfig({resolve:{alias:{'@':new URL('./src',import.meta.url).pathname}},test:{environment:'jsdom',pool:'threads',include:['src/**/*.{test,spec}.{ts,tsx}'],clearMocks:true,restoreMocks:true}});
