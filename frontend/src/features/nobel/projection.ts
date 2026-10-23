export const galleryGeometry = {
  baseScale: 0.42, focusScale: 0.68, depthOffset: 64, top: 8, bottomGap: 12,
} as const

/** 全部卡片在完整旋转周期内的高度上界；与当前角度无关。 */
export function galleryStageHeight(heights: readonly number[]) {
  const { baseScale, focusScale, depthOffset, top, bottomGap } = galleryGeometry
  const measured = heights.length ? heights : [660]
  // y + h*scale 对 proximity 为线性函数，两个端点足以覆盖所有中间位置。
  const bottom = Math.max(...measured.map(height => {
    const h = height || 660 // DOM尚未测量时使用临时值，测量后立即替换。
    return Math.max(depthOffset + h * baseScale, h * (baseScale + focusScale))
  }))
  return Math.ceil(top + bottom + bottomGap)
}

/** 用显示宽度排布弧形展陈，避免圆柱侧缘的投影压缩造成遮挡。 */
export function projectGallery(angle: number, count: number, stageWidth: number) {
  const cardWidth = Math.min(280, stageWidth * 0.7)
  const gap = stageWidth < 600 ? 24 : 36
  const phase = angle / (360 / count)
  const cards = Array.from({ length: count }, (_, index) => {
    const offset = ((index + phase + count / 2) % count + count) % count - count / 2
    const proximity = Math.exp(-offset * offset / 1.7)
    const scale = galleryGeometry.baseScale + galleryGeometry.focusScale * proximity
    return { index, offset, scale, cardWidth, width: cardWidth * scale, x: 0,
      y: (1 - proximity) * galleryGeometry.depthOffset,
      yaw: -48 * Math.tanh(offset / 1.6),
      opacity: Math.max(0, Math.min(1, (3.4 - Math.abs(offset)) / 1.2)) }
  }).sort((a, b) => a.offset - b.offset)

  for (let i = 1; i < cards.length; i++) {
    cards[i].x = cards[i - 1].x + (cards[i - 1].width + cards[i].width) / 2 + gap
  }
  // 在中心两个人物之间插值，跨越主位时不会因切换锚点而跳动。
  const right = cards.findIndex(card => card.offset >= 0)
  const before = cards[Math.max(0, right - 1)]
  const after = cards[right]
  const fraction = before === after ? 0 : -before.offset / (after.offset - before.offset)
  const origin = before.x + (after.x - before.x) * fraction
  return cards.map(card => ({ ...card, x: card.x - origin })).sort((a, b) => a.index - b.index)
}
