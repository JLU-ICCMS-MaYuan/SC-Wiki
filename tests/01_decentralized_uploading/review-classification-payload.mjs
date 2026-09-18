// 跨层回归使用真实分类解析和请求构造；不发起网络请求。
import { build } from '../../frontend/node_modules/esbuild/lib/main.js'

const result = await build({
  entryPoints: [new URL('../../frontend/src/lib/paperReview.ts', import.meta.url).pathname],
  bundle: true, platform: 'node', format: 'esm', write: false,
  plugins: [{ name: 'unused-api', setup(builder) {
    builder.onResolve({ filter: /^\.\/api$/ }, () => ({ path: 'api', namespace: 'fixture' }))
    builder.onLoad({ filter: /.*/, namespace: 'fixture' }, () => ({ contents: 'export const api = {};' }))
  } }],
})
const { resolveReviewClassifications, paperReviewPayload } = await import(
  'data:text/javascript;base64,' + Buffer.from(result.outputFiles[0].text).toString('base64'))
let input = ''
for await (const chunk of process.stdin) input += chunk
const { detail, pendingValues } = JSON.parse(input)
console.log(JSON.stringify(paperReviewPayload('approved', '', resolveReviewClassifications(detail, pendingValues))))
