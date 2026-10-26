import { axisValid, frequency, frequencyPixel, pixelAt, record, type Document } from './engine'

// 只容忍源像素浮点舍入，不把看起来接近零的缺口自动算作零频点。
export const ZERO_PIXEL_TOLERANCE = 1e-4
export type ZeroCurveStatus = 'complete' | 'needs_boundary' | 'needs_confirmation' | 'missing_point'
export type ZeroCurveCheck = {
  id: string; name: string; status: ZeroCurveStatus; pointId?: string
  nearest?: { id: string; frequency: number; distancePx: number }
}
export type ZeroCheck = {
  complete: boolean; boundary: 'confirmed' | 'missing' | 'invalid'; zeroPixel: number
  completedCount: number; curves: ZeroCurveCheck[]
}

/** 从具体保存快照派生结果，不写入“已通过”缓存或修改任何点。 */
export function checkZeroFrequency(doc: Document): ZeroCheck {
  const zeroPixel = pixelAt(doc.calibration.frequency, 0), [x0,y0,x1,y1] = doc.source.plot
  const low = doc.calibration.direction === 'x' ? x0 : y0, high = doc.calibration.direction === 'x' ? x1 : y1
  const valid = axisValid(doc.calibration.frequency) && Number.isFinite(zeroPixel) && zeroPixel >= low && zeroPixel <= high
  const boundary = !valid ? 'invalid' : !doc.zero ? 'missing'
    : Math.abs(doc.zero.pixel - zeroPixel) <= ZERO_PIXEL_TOLERANCE ? 'confirmed' : 'invalid'
  const confirmedIds = new Set(doc.zero?.pointIds || [])
  const curves: ZeroCurveCheck[] = doc.curves.map(curve => {
    let nearest: ZeroCurveCheck['nearest'], confirmed: string | undefined, candidate: string | undefined
    for (const p of curve.points) {
      const distancePx = Math.abs(frequencyPixel(doc,p) - zeroPixel)
      if (!Number.isFinite(distancePx)) continue
      if (!nearest || distancePx < nearest.distancePx) nearest = { id:p.id, frequency:frequency(doc,p), distancePx }
      if (distancePx <= ZERO_PIXEL_TOLERANCE) {
        candidate ||= p.id
        if (confirmedIds.has(p.id)) confirmed ||= p.id
      }
    }
    const status: ZeroCurveStatus = boundary !== 'confirmed' ? 'needs_boundary'
      : confirmed ? 'complete' : candidate ? 'needs_confirmation' : 'missing_point'
    return { id:curve.id, name:curve.name, status, pointId:confirmed || candidate, nearest }
  })
  const completedCount = curves.filter(c => c.status === 'complete').length
  return { complete: curves.length > 0 && completedCount === curves.length, boundary, zeroPixel, completedCount, curves }
}

export function confirmCurrentZeroBoundary(doc: Document): Document {
  const check = checkZeroFrequency(doc)
  if (!axisValid(doc.calibration.frequency) || !Number.isFinite(check.zeroPixel) || check.zeroPixel < doc.source.plot[doc.calibration.direction === 'x' ? 0 : 1]
    || check.zeroPixel > doc.source.plot[doc.calibration.direction === 'x' ? 2 : 3]) throw new Error('当前标定零频线不在图框内，请先核对标定。')
  return record({ ...doc, zero: { pixel:check.zeroPixel, pointIds:check.boundary === 'confirmed' ? doc.zero!.pointIds : [] } },
    'zero-boundary-confirm', `人工确认当前蓝色零频线与原图一致：源像素 ${check.zeroPixel}；不修改标定或点坐标`)
}

export function confirmExistingZeroPoint(doc: Document, curveId: string, pointId: string): Document {
  const check = checkZeroFrequency(doc), curve = doc.curves.find(c => c.id === curveId), point = curve?.points.find(p => p.id === pointId)
  if (check.boundary !== 'confirmed' || !doc.zero) throw new Error('请先在原图上标记零频位置，或确认当前蓝色零频线。')
  if (!point || Math.abs(frequencyPixel(doc,point) - check.zeroPixel) > ZERO_PIXEL_TOLERANCE) throw new Error('选中点尚未落在已确认零频线上，请对照原图调整或补选；不会自动移动它。')
  return record({ ...doc, zero: { ...doc.zero, pointIds:[...new Set([...doc.zero.pointIds, pointId])] } },
    'zero-point-confirm', `${curve!.name}：人工确认已有点 ${pointId} 位于零频边界，坐标保持不变`)
}
