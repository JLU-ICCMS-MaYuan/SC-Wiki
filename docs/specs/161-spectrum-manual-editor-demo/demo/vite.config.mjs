import { defineConfig } from '../../../../frontend/node_modules/vite/dist/node/index.js'
import { fileURLToPath } from 'node:url'
const dependency = name => fileURLToPath(new URL('../../../../frontend/node_modules/' + name, import.meta.url))
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: [
    { find: /^react$/, replacement: dependency('react/index.js') },
    { find: /^react\/jsx-runtime$/, replacement: dependency('react/jsx-runtime.js') },
    { find: /^react\/jsx-dev-runtime$/, replacement: dependency('react/jsx-dev-runtime.js') },
    { find: /^react-dom\/client$/, replacement: dependency('react-dom/client.js') },
    { find: /^react-dom$/, replacement: dependency('react-dom/index.js') },
  ] },
  test: { include: ['tests/*.test.ts'], environment: 'node' },
  server: { host: '127.0.0.1', port: 5187, strictPort: true },
  build: { outDir: 'dist', emptyOutDir: true },
})
