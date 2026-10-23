import { useEffect, useId, useState } from 'react'
import { Alert, Box, Typography } from '@mui/material'
import type { PropertySpectrumCurve as Curve, PropertySpectrumItem as Item } from '../lib/propertySpectra'
import { spectrumGeometry, spectrumPixelPath, spectrumCurveColor } from '../lib/spectrumGeometry'

const number = (v: number) => Number.isFinite(v) ? Number(v.toFixed(2)).toString() : '—'

export default function SpectrumFigure({ item, curves, allCurves, image, mode, opacity }: { item: Item; curves: Curve[]; allCurves: Curve[]; image: string; mode: string; opacity: number }) {
  const id = useId().replace(/:/g, '')
  const [pixels, setPixels] = useState<{ image: string; width: number; height: number; data: Uint8ClampedArray } | null>(null)
  const [imageFailure, setImageFailure] = useState(false)
  useEffect(() => {
    let active = true
    setPixels(null); setImageFailure(false)
    if (!image) return
    const img = new Image()
    img.onload = () => {
      if (!active) return
      try {
        const canvas = document.createElement('canvas'); canvas.width = img.naturalWidth; canvas.height = img.naturalHeight
        const context = canvas.getContext('2d', { willReadFrequently: true })
        if (!context) throw new Error('无法读取图像像素')
        context.drawImage(img, 0, 0)
        setPixels({ image, width: canvas.width, height: canvas.height, data: context.getImageData(0, 0, canvas.width, canvas.height).data })
      } catch { setImageFailure(true) }
    }
    img.onerror = () => { if (active) setImageFailure(true) }
    img.src = image
    return () => { active = false }
  }, [image])
  const size = item.source.size_px
  const loaded = pixels?.image === image ? pixels : null
  if (loaded && size && (size[0] !== loaded.width || size[1] !== loaded.height)) return <Alert severity="warning">原图尺寸与标定不一致，不能保证叠加位置，请重新核对。</Alert>
  const width = size?.[0] || loaded?.width || 0, height = size?.[1] || loaded?.height || 0
  const geometry = spectrumGeometry(allCurves, width, height, loaded?.data)
  if (!geometry) return <>
    <Alert severity="info">尚未定位当前谱的子图范围，不能保证裁切和叠加；请核对标定。</Alert>
    {mode === 'source' && image && <Box component="img" src={image} alt="论文谱原图" sx={{ maxWidth: '100%', maxHeight: 520, mt: 1 }} />}
  </>
  if (mode !== 'data' && !image) return <Typography color="text.secondary">原图正在读取或暂不可用；可重试读取。</Typography>
  const curve = allCurves[0], direction = curve.frequency_direction
  if (!direction || !curve.axis_calibration) return <Alert severity="info">缺少来源坐标标定，暂不能准确绘制。</Alert>
  const { plot, crop } = geometry
  const pw = plot[2] - plot[0], ph = plot[3] - plot[1]
  const x0 = Math.min(crop[0], plot[0] - 56), y0 = crop[1] - 14
  const vw = crop[2] - x0 + 12, vh = crop[3] - y0 + 32
  const calibration = item.result.calibration?.curves?.find((value: { id: string }) => value.id === curve.id)
  const uncertainAmplitude = curve.kind === 'alpha2f' && !calibration?.amplitude_evidence
  const factor = ({ THz: 1, 'cm-1': .0299792458, meV: .2417989242084918 } as Record<string, number>)[calibration?.frequency_unit || 'THz'] || 1
  const frequencyTicks: number[][] = calibration?.frequency_ticks || []
  const fAxis = curve.axis_calibration.frequency, aAxis = curve.axis_calibration.amplitude
  const fBounds = direction === 'y' ? [plot[1], plot[3]] : [plot[0], plot[2]]
  const aBounds = direction === 'y' ? [plot[0], plot[2]] : [plot[1], plot[3]]
  const ticks = frequencyTicks.length ? frequencyTicks.map(([p, value]) => [p, value * factor])
    : Array.from({ length: 5 }, (_, i) => { const p = fBounds[0] + (fBounds[1] - fBounds[0]) * i / 4; return [p, fAxis.slope * p + fAxis.intercept] })
  const amplitudeLabel = curve.kind === 'alpha2f' ? uncertainAmplitude ? 'α²F（幅值刻度待核对）' : 'α²F'
    : curve.kind === 'cumulative_lambda' ? '累计 λ' : curve.unit === 'pixel' ? 'DOS / 相对幅值（像素）' : `DOS / ${curve.unit}`
  const paths = curves.map((value, i) => ({ value, color: spectrumCurveColor(value, i), path: spectrumPixelPath(value) }))
  return <>
    <Box component="svg" role="img" aria-label={mode === 'source' ? '论文谱原图' : mode === 'overlay' ? '原图与提取数据叠加' : `提取谱数据，频率沿${direction === 'y' ? '竖轴' : '横轴'}，与来源图一致`}
      data-crop-method={geometry.method} data-crop-box={crop.join(',')} data-plot-box={plot.join(',')} data-plot-ratio={pw / ph}
      viewBox={`${x0} ${y0} ${vw} ${vh}`} preserveAspectRatio="xMidYMid meet"
      sx={{ width: '100%', height: 'auto', maxWidth: 520 * vw / vh, display: 'block', mx: 'auto', overflow: 'visible' }}>
      <defs><clipPath id={`${id}-crop`}><rect x={crop[0]} y={crop[1]} width={crop[2] - crop[0]} height={crop[3] - crop[1]} /></clipPath>
        <clipPath id={`${id}-plot`}><rect x={plot[0]} y={plot[1]} width={pw} height={ph} /></clipPath></defs>
      <rect x={x0} y={y0} width={vw} height={vh} fill="white" />
      {mode !== 'data' && <image href={image} width={width} height={height} clipPath={`url(#${id}-crop)`} />}
      {mode === 'data' && <rect x={plot[0]} y={plot[1]} width={pw} height={ph} fill="none" stroke="#94a3b8" vectorEffect="non-scaling-stroke" />}
      {mode !== 'source' && <g clipPath={`url(#${id}-plot)`} opacity={mode === 'overlay' ? opacity : 1}>
        {paths.map(({ value, path, color }) => <g key={value.id}>
          {mode === 'overlay' && <path d={path} fill="none" stroke="white" strokeWidth={3.6} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />}
          <path data-spectrum-path={value.id} d={path} fill="none" stroke={color} strokeWidth={mode === 'overlay' ? 1.9 : 1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </g>)}
      </g>}
      {ticks.filter(([p]) => p >= fBounds[0] - 2 && p <= fBounds[1] + 2).map(([p, value], i) => <text key={i} x={direction === 'y' ? plot[0] - 8 : p} y={direction === 'y' ? p + 3 : crop[3] + 14} textAnchor={direction === 'y' ? 'end' : 'middle'} fontSize={10} fill="#64748b">{number(value)}</text>)}
      {mode === 'data' && !uncertainAmplitude && Array.from({ length: 3 }, (_, i) => {
        const p = aBounds[0] + (aBounds[1] - aBounds[0]) * i / 2
        return <text key={i} x={direction === 'y' ? p : plot[0] - 8} y={direction === 'y' ? plot[3] + 16 : p + 3} textAnchor={direction === 'y' ? 'middle' : 'end'} fontSize={10} fill="#64748b">{number(aAxis.slope * p + aAxis.intercept)}</text>
      })}
      {direction === 'y' ? <>
        <text transform={`translate(${plot[0] - 43},${plot[1] + ph / 2}) rotate(-90)`} textAnchor="middle" fontSize={11}>频率 / THz</text>
        {mode === 'data' && <text x={plot[0] + pw / 2} y={crop[3] + 20} textAnchor="middle" fontSize={10}>{amplitudeLabel}</text>}
      </> : <><text x={plot[0] + pw / 2} y={crop[3] + 28} textAnchor="middle" fontSize={11}>频率 / THz</text>
        {mode === 'data' && <text x={plot[0]} y={plot[1] - 7} fontSize={10}>{amplitudeLabel}</text>}</>}
    </Box>
    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
      {mode === 'overlay' ? '彩色描边为提取数据，白色细底线用于区分原曲线；缺失点不连线。' : mode === 'source' ? '仅显示当前材料状态、当前谱类型的子图；旁侧频率轴按已有刻度重绘。' : '图框比例和坐标位置沿用原图，不按曲线峰值拉伸。'}
    </Typography>
    {(geometry.method === 'roi' || imageFailure) && <Typography variant="caption" color="warning.main">子图边框尚未独立确认，当前按已有提取区域显示。</Typography>}
  </>
}
