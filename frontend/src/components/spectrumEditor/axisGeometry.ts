import { amplitudePixel, frequencyPixel, pixelAt, valueAt, type Axis, type Document, type Point } from './engine'

export type Tick = { pixel: number; value: number }
export function recognizedAxes(doc: Document) {
  const recognized=doc.recognizedAxes
  return recognized && doc.source.id === recognized.sourceId && doc.source.sha256 === recognized.sourceSha256 ? recognized : null
}
/** 当前标定生成的刻度与识别记录分开，不能把等分数值标作 AI 识别。 */
export function currentTicks(axis: Axis, low: number, high: number): Tick[] {
  const values = Array.from({ length: 5 }, (_, i) => axis.values[0] + (axis.values[1] - axis.values[0]) * i / 4)
  if (!values.some(v => Math.abs(v) < 1e-9)) values.push(0)
  return values.map(value => ({ pixel: pixelAt(axis, value), value })).filter(t => Number.isFinite(t.pixel) && t.pixel >= low - 1e-6 && t.pixel <= high + 1e-6)
}
export function pointReadout(doc: Document, point: Point) {
  return {
    x: point.x, y: point.y,
    frequency: valueAt(doc.calibration.frequency, frequencyPixel(doc, point)),
    amplitude: valueAt(doc.calibration.amplitude, amplitudePixel(doc, point)),
  }
}
