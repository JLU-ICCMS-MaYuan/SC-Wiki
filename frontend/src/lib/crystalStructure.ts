import type { GLModel, Matrix3, Vector3 } from '3dmol'

export interface CrystalStructureData {
  parameters: number[]
  lattice: number[][]
  volume: number
  atoms: Array<{ element: string; cartesian: number[]; fractional: number[] }>
}

/** 3Dmol 2.5 的 VASP 解析器把按行读入的基向量直接传给 Matrix3；原子坐标却按列变换。 */
export function normalizeCrystalMatrix(model: Pick<GLModel, 'getCrystData' | 'setCrystMatrix'>, format: string) {
  if (format === 'vasp') {
    const matrix = model.getCrystData()?.matrix as Matrix3 | undefined
    if (matrix) model.setCrystMatrix(matrix.clone().transpose())
  }
}

/** 同一已解析模型生成展示数据；POSCAR 的晶胞只有矩阵，没有单独的六参数。 */
export function crystalStructureData(model: Pick<GLModel, 'getCrystData' | 'selectedAtoms'>, math: { Matrix3: typeof Matrix3; Vector3: typeof Vector3 }): CrystalStructureData | null {
  const crystal = model.getCrystData()
  if (!crystal?.matrix) return null
  const matrix = crystal.matrix as Matrix3
  const elements = Array.from(matrix.elements)
  const volume = Math.abs(matrix.getDeterminant())
  if (elements.length !== 9 || !elements.every(Number.isFinite) || !Number.isFinite(volume) || volume <= 0) return null
  // 3Dmol 按列存放基向量，界面按 a/b/c 向量逐行排列。
  const lattice = [0, 1, 2].map(index => elements.slice(index * 3, index * 3 + 3))
  const vectors = lattice.map(([x, y, z]) => new math.Vector3(x, y, z))
  const lengths = vectors.map(vector => vector.length())
  const angle = (a: number, b: number) => Math.acos(Math.max(-1, Math.min(1, vectors[a].dot(vectors[b]) / (lengths[a] * lengths[b])))) * 180 / Math.PI
  const inverse = new math.Matrix3().getInverse3(matrix)
  const atoms = model.selectedAtoms({}).map(atom => {
    const fractional = new math.Vector3(atom.x, atom.y, atom.z).applyMatrix3(inverse)
    return { element: atom.elem || '?', cartesian: [atom.x ?? NaN, atom.y ?? NaN, atom.z ?? NaN], fractional: [fractional.x, fractional.y, fractional.z] }
  })
  if (!atoms.length || atoms.some(atom => ![...atom.cartesian, ...atom.fractional].every(Number.isFinite))) return null
  return { parameters: [...lengths, angle(1, 2), angle(0, 2), angle(0, 1)], lattice, volume, atoms }
}

export const crystalNumber = (value: number) => (Math.abs(value) < 0.000005 ? 0 : value).toFixed(4)
