// 本地与 CI 共用的表单约束检查；回退注入仅在临时编译器中生效，不修改工作树。
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const vitest = join(root, 'frontend/node_modules/vitest/vitest.mjs')
const suites = ['form-contract', 'physical-method-hosts', 'graph-title-form', 'paper-field-settings', 'two-stage-review', 'state-review-convergence', 'parsing-triage-removal',
  'sidebar-field-save', 'sidebar-field-workflow', 'sidebar-field-hosts', 'field-sidebar-ownership', 'field-red-marking', 'sidebar-feedback']
const paths = suites.map(name => `tests/01_decentralized_uploading/${name}.test.tsx`)
if (!process.argv.includes('--mutation')) {
  const result = spawnSync(process.execPath, [vitest, 'run', '--config', join(root, 'vitest.config.ts'), ...paths], { cwd: root, stdio: 'inherit' })
  if (result.error) throw result.error
  process.exit(result.status ?? 1)
}
const temporary = mkdtempSync(join(tmpdir(), 'scwiki-form-contract-'))
try {
  const config = join(temporary, 'mutation.config.ts'), report = join(temporary, 'result.json')
  const marker = "const environment = { catalogs, catalogLoading, catalogError, spaceGroups, paperType, readOnly, fixedContract, lang, dict }"
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
  const colorReport = join(temporary, 'color-result.json')
  const colorMarker = "  if (record.local_modified || record.manual_pending) return 'attention'"
  const colorSource = readFileSync(join(root, 'frontend/src/lib/evidenceStatus.ts'), 'utf8')
  if (!colorSource.includes(colorMarker)) throw new Error('标红回退注入位置变化；请更新注入器。')
  writeFileSync(config, `import config from ${JSON.stringify(join(root, 'vitest.config.ts'))};
export default {...config, plugins:[...config.plugins,{name:'known-color-regression',enforce:'pre',transform(code,id){
if(!id.endsWith('/src/lib/evidenceStatus.ts'))return null;
return code.replace(${JSON.stringify(colorMarker)},'');
}}]};`)
  const colors = spawnSync(process.execPath, [vitest, 'run', '--config', config, paths[0], '-t', '220 .*宿主标红', '--reporter=json', '--outputFile', colorReport], { cwd: root, encoding: 'utf8' })
  if (colors.error) throw colors.error
  const colorData = JSON.parse(readFileSync(colorReport, 'utf8'))
  const colorFailures = colorData.testResults.flatMap(suite => suite.assertionResults).filter(test => test.status === 'failed')
  if (colors.status === 0 || colorFailures.length !== 4 || !colorFailures.every(test => test.fullName.includes('宿主标红')
      && test.failureMessages.some(message => message.includes('data-evidence-caption-problem')))) {
    process.stderr.write(colors.stdout + colors.stderr)
    throw new Error('未证明四宿主检查拦住原免审项编辑漏红；环境或编译失败不算检出。')
  }
  console.log('通过：8 项完整宿主渲染回退、4 项原免审字段漏红回退均检出；工作树未修改。')
} finally { rmSync(temporary, { recursive: true, force: true }) }
