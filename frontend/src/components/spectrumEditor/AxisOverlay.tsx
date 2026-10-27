import { currentTicks, recognizedAxes } from './axisGeometry'
import { pixelAt, type Document, type Point } from './engine'

const display = (value: number) => Number(value.toFixed(4)).toString()
const blue = '#087fa5', gray = '#778394', amber = '#a56d15'

export default function AxisOverlay({ doc, scale, point }: { doc: Document; scale: number; point?: Point }) {
  const [x0,y0,x1,y1] = doc.source.plot, vertical = doc.calibration.direction === 'y', ref = recognizedAxes(doc)
  const unit = doc.calibration.amplitude.unit === 'pixel' ? '相对像素' : doc.calibration.amplitude.unit
  const frequencyTicks = currentTicks(doc.calibration.frequency, vertical ? y0 : x0, vertical ? y1 : x1)
  const amplitudeTicks = currentTicks(doc.calibration.amplitude, vertical ? x0 : y0, vertical ? x1 : y1)
  const azero = pixelAt(doc.calibration.amplitude, 0)
  const line = (props: React.SVGProps<SVGLineElement>) => <line strokeWidth={1.2} vectorEffect="non-scaling-stroke" {...props}/>
  // 窄图窗只减少当前标定的辅助标签；已有识别刻度仍全部显示。
  const readableTicks = (values: {pixel:number;value:number}[], horizontal: boolean) => {
    if (!horizontal) return values
    const sorted=[...values].sort((a,b)=>a.pixel-b.pixel), selected: typeof values=[]
    const priority=[...sorted.filter(t=>t.value===0),sorted[0],sorted.at(-1),sorted[Math.floor(sorted.length/2)],...sorted]
    for(const tick of priority) if(tick && !selected.includes(tick) && selected.every(other=>Math.abs(other.pixel-tick.pixel)*scale > (display(other.value).length+display(tick.value).length)*3+6)) selected.push(tick)
    return selected.sort((a,b)=>a.pixel-b.pixel)
  }
  const ticks = (values: {pixel:number;value:number}[], along: 'x'|'y', color: string, id: string, reference = false, top = false) => values.map(({pixel,value}, i) => {
    const horizontal = along === 'x'
    return <g key={i} data-axis-tick={id} data-pixel={pixel} data-value={value}>
      {line(horizontal ? {x1:pixel,x2:pixel,y1:top?y0:y1,y2:(top?y0:y1)+(reference?5:-5)/scale,stroke:color} : {x1:x0,x2:x0+(reference?-5:5)/scale,y1:pixel,y2:pixel,stroke:color})}
      <text x={horizontal?pixel:x0-(reference?31:7)/scale} y={horizontal?(top?y0:y1)+(reference?16:-9)/scale:pixel+3/scale}
        textAnchor={horizontal?'middle':'end'} fontSize={10/scale} fill={color}>{display(value)}</text>
    </g>
  })
  return <g data-testid="axes-overlay" pointerEvents="none" style={{paintOrder:'stroke',stroke:'#fff',strokeWidth:3/scale,strokeLinejoin:'round'}}>
    {ref && <g data-testid="recognized-axes">
      {ticks(ref.frequencyTicks.map(([pixel,value])=>({pixel,value})), ref.direction as 'y', gray, 'recognized-frequency', true)}
      {Boolean(ref?.lambdaTicks.length) && <>
        {ticks(ref.lambdaTicks.map(([pixel,value])=>({pixel,value})), 'x', amber, 'recognized-lambda', true)}
        <text x={(x0+x1)/2} y={y1+33/scale} textAnchor="middle" fontSize={10/scale} fill={amber}>累计 λ · 识别参考</text>
      </>}
    </g>}
    <g data-testid="current-axes" data-frequency-direction={doc.calibration.direction} stroke={blue}>
      {line({x1:x0,x2:x0,y1:y0,y2:y1})}{line({x1:x0,x2:x1,y1:vertical?y0:y1,y2:vertical?y0:y1})}
    </g>
    {ticks(readableTicks(frequencyTicks,!vertical), vertical?'y':'x',blue,'current-frequency')}
    {ticks(readableTicks(amplitudeTicks,vertical), vertical?'x':'y',blue,'current-amplitude',false,vertical)}
    <text transform={`translate(${x0-49/scale},${(y0+y1)/2}) rotate(-90)`} textAnchor="middle" fontSize={10/scale} fill={blue}>
      {vertical ? `频率 / ${doc.calibration.frequency.unit}` : `幅值 / ${unit}`} · 当前标定
    </text>
    <text x={(x0+x1)/2} y={vertical?y0-23/scale:y1+(Boolean(ref?.lambdaTicks.length)?48:33)/scale} textAnchor="middle" fontSize={10/scale} fill={blue}>
      {vertical ? `幅值 / ${unit}` : `频率 / ${doc.calibration.frequency.unit}`} · 当前标定
    </text>
    {point && <g data-testid="selected-point-projection" stroke="#6366c4">
      {line({x1:point.x,x2:x0,y1:point.y,y2:point.y,strokeDasharray:'3 4',opacity:.7})}
      {line({x1:point.x,x2:point.x,y1:point.y,y2:vertical?y0:y1,strokeDasharray:'3 4',opacity:.7})}
    </g>}
    {Number.isFinite(azero) && <desc>幅值零位置 {azero}；当前幅值单位 {unit}。识别参考不会替换当前标定。</desc>}
  </g>
}
