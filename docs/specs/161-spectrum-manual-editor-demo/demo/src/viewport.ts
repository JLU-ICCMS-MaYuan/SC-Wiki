import type { Rect } from './engine'

/** 边距以屏幕像素计算，与轴文字的固定字号一致；工具栏和说明在 SVG 外。 */
export function fitViewport(crop: Rect, width: number, height: number, axes = true): Rect {
  const [x,y,w,h] = crop, left = axes ? 64 : 12, right = 18, top = axes ? 36 : 12, bottom = axes ? 48 : 12
  const scale = Math.min(Math.max(1,width-left-right)/w, Math.max(1,height-top-bottom)/h)
  const extraX = (width-left-right-w*scale)/2, extraY = (height-top-bottom-h*scale)/2
  return [x-(left+extraX)/scale, y-(top+extraY)/scale, width/scale, height/scale]
}

export function zoomViewport(view: Rect, fit: Rect, factor: number, anchor?: {x:number;y:number}): Rect {
  const width = Math.max(fit[2]/24, Math.min(fit[2]*2,view[2]*factor)), ratio = width/view[2]
  const x = anchor?.x ?? view[0]+view[2]/2, y = anchor?.y ?? view[1]+view[3]/2
  return [x-(x-view[0])*ratio, y-(y-view[1])*ratio, width,view[3]*ratio]
}

export const wheelPixels = (delta: number, mode: number, height: number) => delta*(mode===1?16:mode===2?height:1)
export const wheelFactor = (pixels: number) => Math.exp(Math.max(-2000,Math.min(2000,pixels))*.00035)
