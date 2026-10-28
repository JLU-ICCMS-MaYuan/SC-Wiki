// 本地与 CI 共用的表单约束检查；回退注入仅在临时编译器中生效，不修改工作树。
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const vitest = join(root, 'frontend/node_modules/vitest/vitest.mjs')
const suites = ['form-contract', 'graph-title-form', 'paper-field-settings', 'two-stage-review', 'state-review-convergence', 'parsing-diagnostics']
const paths = suites.map(name => `tests/01_decentralized_uploading/${name}.test.tsx`)
if (!process.argv.includes('--mutation')) {
  const result = spawnSync(process.execPath, [vitest, 'run', '--config', join(root, 'vitest.config.ts'), ...paths], { cwd: root, stdio: 'inherit' })
  if (result.error) throw result.error
  process.exit(result.status ?? 1)
}
const temporary = mkdtempSync(join(tmpdir(), 'scwiki-form-contract-'))
try {
  const config = join(temporary, 'mutation.config.ts'), report = join(temporary, 'result.json')
  const marker = "const environment = { catalogs, catalogLoading, catalogError, spaceGroups, paperType, readOnly, lang, dict }"
  const source = readFileSync(join(root, 'frontend/src/components/MaterialStatesEditor.tsx'), 'utf8')
  if (!source.includes(marker)) throw new Error('回退注入位置已变化；请更新注入器，不能跳过此检查。')
  writeFileSync(config, `import config from ${JSON.stringify(join(root, 'vitest.config.ts'))};
export default {...config, plugins:[...config.plugins,{name:'known-form-regression',enforce:'pre',transform(code,id){
if(!id.endsWith('/src/components/MaterialStatesEditor.tsx'))return null;
return code.replace(${JSON.stringify(marker)},${JSON.stringify(marker.replace('lang, dict }', 'lang, dict, reviewFields: [...(reviewFields || [])] }'))});
}}]};`)
  const result = spawnSync(process.execPath, [vitest, 'run', '--config', config, paths[0], '-t', '完整宿主：', '--reporter=json', '--outputFile', report], { cwd: root, encoding: 'utf8' })
  if (result.error) throw result.error
  const data = JSON.parse(readFileSync(report, 'utf8'))
  const failures = data.testResults.flatMap(suite => suite.assertionResults).filter(test => test.status === 'failed')
  if (result.status === 0 || failures.length !== 8 || !failures.every(test => test.fullName.includes('完整宿主：') && test.failureMessages.some(message => message.includes('AssertionError')))) {
    process.stderr.write(result.stdout + result.stderr)
    throw new Error('未证明八项完整宿主检查拦住已知渲染回退；环境或编译失败不算检出。')
  }
  console.log('通过：注入新数组导致整体缓存失效后，四类宿主的 8 项行为回归均检出失败；工作树未修改。')
} finally { rmSync(temporary, { recursive: true, force: true }) }
