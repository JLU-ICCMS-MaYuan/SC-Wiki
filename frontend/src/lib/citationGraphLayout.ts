export interface GraphPosition { x: number; y: number }

/** 默认坐标由稳定身份决定；后续只为新增节点寻找空位。 */
export function allocateGraphPositions(
  ids: string[], occupied: GraphPosition[], columns: number,
): Map<string, GraphPosition> {
  const positions = new Map<string, GraphPosition>()
  const used = [...occupied]
  let slot = 0
  for (const id of [...ids].sort((a, b) => Number(a.replace('paper:', '')) - Number(b.replace('paper:', '')))) {
    let position: GraphPosition
    do {
      const row = Math.floor(slot / Math.max(1, columns))
      const signedRow = row % 2 ? Math.ceil(row / 2) : -Math.floor(row / 2)
      position = { x: (slot % Math.max(1, columns)) * 380, y: signedRow * 190 }
      slot += 1
    } while (used.some(p => Math.abs(p.x - position.x) < 320 && Math.abs(p.y - position.y) < 150))
    positions.set(id, position)
    used.push(position)
  }
  return positions
}
