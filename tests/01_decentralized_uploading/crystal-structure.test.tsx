import { afterAll, expect, it, vi } from 'vitest'
import { Matrix3, Vector3, GLModel } from '../../frontend/node_modules/3dmol/build/3Dmol.js'
import { crystalStructureData, normalizeCrystalMatrix, crystalNumber } from '../../frontend/src/lib/crystalStructure'

const originalCreateObjectURL = vi.hoisted(() => {
  const original = URL.createObjectURL
  URL.createObjectURL = () => 'blob:unused-surface-worker'
  return original
})
afterAll(() => { URL.createObjectURL = originalCreateObjectURL })

it.each(['Direct', 'Cartesian'])('非正交 POSCAR 的 %s 坐标、晶格向量、参数与模型同源', mode => {
  const coordinates = mode === 'Direct' ? '0.25 0.5 0.75' : '2.625 2.1875 4.5'
  const model = new GLModel()
  model.addMolData(`Sn\n1\n7 0 0\n1 4 0\n0.5 0.25 6\nSn\n2\n${mode}\n0 0 0\n${coordinates}\n`, 'vasp')
  normalizeCrystalMatrix(model, 'vasp')
  const result = crystalStructureData(model, { Matrix3, Vector3 })!
  expect(result.lattice).toEqual([[7, 0, 0], [1, 4, 0], [0.5, 0.25, 6]])
  expect(result.atoms[1].cartesian).toEqual([2.625, 2.1875, 4.5])
  result.atoms[1].fractional.forEach((value, index) => expect(value).toBeCloseTo([0.25, 0.5, 0.75][index], 6))
  expect(result.volume).toBeCloseTo(168)
  expect(result.parameters[1]).toBeCloseTo(Math.sqrt(17))
  expect(result.parameters[5]).toBeCloseTo(Math.acos(1 / Math.sqrt(17)) * 180 / Math.PI)
})

it('无晶胞、退化矩阵、空原子和非法坐标不生成虚假参数', () => {
  const model = { getCrystData: () => null, selectedAtoms: () => [] }
  expect(crystalStructureData(model, { Matrix3, Vector3 })).toBeNull()
  for (const matrix of [new Matrix3().multiplyScalar(0), new Matrix3()]) {
    expect(crystalStructureData({ ...model, getCrystData: () => ({ matrix }) }, { Matrix3, Vector3 })).toBeNull()
  }
  expect(crystalNumber(-0.0000001)).toBe('0.0000')
})
