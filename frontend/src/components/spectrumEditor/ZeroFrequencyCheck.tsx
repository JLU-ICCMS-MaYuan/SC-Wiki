import type { ZeroCheck, ZeroCurveCheck } from './zeroCheck'

const messages = {
  complete: '零频位置核对完成',
  needs_boundary: '尚未确认原图零频位置',
  needs_confirmation: '已有零频点，等待人工确认',
  missing_point: '缺少位于零频线上的有效点',
}
const number = (value: number) => Math.abs(value) > 0 && Math.abs(value) < .0001 ? value.toExponential(2) : Number(value.toFixed(4)).toString()

export default function ZeroFrequencyCheck({ result, unit, afterSave, onContinue, readOnly=false }: {
  result: ZeroCheck; unit: string; afterSave: boolean; readOnly?: boolean; onContinue: (curve: ZeroCurveCheck) => void
}) {
  return <section className="zero-check" data-testid="saved-zero-check" data-complete={result.complete}>
    <div className={'callout '+(result.complete?'success':'warning')} role="status" data-testid="saved-zero-summary">
      <strong>{result.complete ? '零频位置核对完成' : '零频位置核对未完成'}</strong>
      <span>{afterSave ? '本次保存后自动检查' : '按当前保存记录检查'} · {result.completedCount}/{result.curves.length} 条曲线完成</span>
    </div>
    <p className="muted">{result.boundary === 'confirmed' ? Number.isFinite(result.zeroPixel) ? `已记录原图零频位置：${number(result.zeroPixel)} px。` : '各曲线已分别记录原图零频位置。'
      : result.boundary === 'invalid' ? '零频标定与图框或人工记录不一致，请重新核对。' : '仅有识别或蓝色标定线不代表已人工核对；可在编辑器中直接确认现有线。'}</p>
    <div className="zero-check-rows">{result.curves.map(curve => <div className="zero-check-row" key={curve.id} data-zero-curve={curve.id} data-state={curve.status}>
      <div><strong>{curve.name}</strong><span>{messages[curve.status]}</span>
        {curve.nearest && <small>最近点：{number(curve.nearest.frequency)} {unit} · 距零线 {number(curve.nearest.distancePx)} px</small>}
      </div>
      {curve.status !== 'complete' && !readOnly && <button onClick={() => onContinue(curve)}>继续核对 {curve.name}</button>}
    </div>)}</div>
    <p className="muted">本检查只核对零频位置与选点的一致性，不代表整谱已采纳或积分条件已满足。未完成不影响人工修订保存。</p>
  </section>
}
