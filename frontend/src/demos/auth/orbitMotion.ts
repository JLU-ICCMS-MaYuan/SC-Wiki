export const TAU = Math.PI * 2
export const DEFAULT_SPEED = TAU / 12_000
export const RESTART_SPEED = TAU / 20_000
export const MAX_SPEED = TAU / 4_000
export interface OrbitMotion { angle: number; speed: number; target: number | null }
export const normalizeAngle = (angle: number) => ((angle % TAU) + TAU) % TAU

export function pushOrbit(motion: OrbitMotion, restart: boolean) {
  motion.speed = restart ? RESTART_SPEED : Math.min(MAX_SPEED, motion.speed * 1.35)
  motion.target = null
}

// 沿当前方向前进，在跨过目标的这一帧精确停靠，不能越过后再绕一圈。
export function advanceOrbit(motion: OrbitMotion, milliseconds: number): boolean {
  if (motion.speed <= 0) return false
  const distance = motion.speed * Math.max(0, milliseconds)
  if (motion.target !== null && distance >= normalizeAngle(motion.target - motion.angle)) {
    motion.angle = normalizeAngle(motion.target)
    motion.speed = 0
    motion.target = null
    return true
  }
  motion.angle = normalizeAngle(motion.angle + distance)
  return false
}
