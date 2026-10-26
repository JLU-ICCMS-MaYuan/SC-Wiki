// 手动调参入口：只改下面这四个值，界面说明与拖动权重会共用同一配置。
export const DRAG_INFLUENCE = {
  coreNeighbors: 3,    // 选中点两侧各几个点明显跟随；正整数。
  edgeWeight: 0.6,     // 主要影响区最外一个点的跟随比例；0 < 值 <= 1。
  decayLength: 2,     // 指数衰减长度（点数）；越小衰减越快，必须 > 0。
  minWeight: 0.001,   // 小于该跟随比例就不再移动；0 < 值 < edgeWeight。
}

export function createInfluenceKernel(config: typeof DRAG_INFLUENCE): number[] {
  const { coreNeighbors, edgeWeight, decayLength, minWeight } = config
  if (!Object.values(config).every(Number.isFinite) || !Number.isInteger(coreNeighbors) || coreNeighbors < 1
    || edgeWeight <= 0 || edgeWeight > 1 || decayLength <= 0 || minWeight <= 0 || minWeight >= edgeWeight) {
    throw new Error('联动参数无效：邻点数须为正整数，跟随比例在(0,1]，衰减长度须为正数，截断值须小于跟随比例。')
  }
  const end = Math.ceil(coreNeighbors + decayLength * Math.log(edgeWeight / minWeight))
  if (!Number.isFinite(end) || end > 1000) throw new Error('联动范围过大：请减小邻点数或衰减长度，或增大 minWeight。')
  // 只在加载配置时生成一次；选中点始终100%跟随，拖动过程中不重复计算指数。
  return Array.from({ length: end + 1 }, (_, distance) => distance <= coreNeighbors
    ? 1 - (1 - edgeWeight) * (distance / coreNeighbors)
    : edgeWeight * Math.exp(-(distance - coreNeighbors) / decayLength))
    .filter(weight => weight >= minWeight)
}
