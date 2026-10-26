import { useId } from 'react'

export default function ImageOpacityControl({ value, onChange, disabled }: {
  value: number; onChange: (value: number) => void; disabled: boolean
}) {
  const hint = useId()
  return <label className={'image-opacity-control'+(disabled?' is-disabled':'')} data-testid="image-opacity-control">
    <span className="opacity-title">原图<br/>不透明度</span>
    <output>{value}%</output>
    <span className="opacity-end">100</span>
    <input type="range" min={0} max={100} step={1} value={value} disabled={disabled}
      aria-label="原图不透明度" aria-orientation="vertical" aria-valuetext={value+'%'} aria-describedby={hint}
      title="0% 完全透明，100% 完全不透明" onChange={event => onChange(Number(event.target.value))}/>
    <span className="opacity-end">0</span>
    <span id={hint} className="opacity-hint">{disabled?'原图已隐藏':'上下拖动'}</span>
  </label>
}
