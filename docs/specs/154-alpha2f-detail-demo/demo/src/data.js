// 合成的已知谱：只用于交互和数值显示验证，不对应任何材料测量。
const gaussian = (x, center, width) => Math.exp(-(((x - center) / width) ** 2));
const samples = Array.from({ length: 281 }, (_, i) => {
  const f = i * 0.25;
  // 合成谱显式设定低频 O(f²)，仅此已知极限允许在零频使用积分端点极限。
  const envelope = f * f / (f * f + 1);
  const original = envelope * (0.32 * gaussian(f, 11, 4) + 1.05 * gaussian(f, 28, 5) + 0.7 * gaussian(f, 45, 9) + 0.28 * gaussian(f, 59, 3));
  const a = original * (0.975 + 0.08 * (f / 70 - 0.5) + 0.013 * Math.sin(f * 1.8));
  const d0 = envelope * (0.85 * gaussian(f, 7, 3) + 0.18 * gaussian(f, 18, 3));
  const d1 = envelope * (0.65 * gaussian(f, 15, 4) + 0.22 * gaussian(f, 24, 3));
  const d2 = envelope * (0.9 * gaussian(f, 38, 8) + 0.65 * gaussian(f, 54, 6));
  return { id: i + 1, f, original, a, diff: Math.abs(a - original), d0, d1, d2 };
});
export function area(data, fields) {
  if (data.some(row => fields.some(key => !Number.isFinite(row[key])))) return null;
  return data.slice(1).reduce((sum, row, i) => sum + (row.f - data[i].f) * fields.reduce((total, key) => total + row[key] + data[i][key], 0) / 2, 0);
}
// 先构造已知 3N 的合成来源谱，再施加提取偏差；不事后把提取结果缩放到 3N。
export const dosModel = { atoms: 27, target: 81, tolerance: 0.01, unit: 'states/(THz·cell)' };
const sourceScale = dosModel.target / area(samples, ['d0', 'd1', 'd2']);
export const rows = samples.map(row => {
  const d0 = row.d0 * sourceScale, d1 = row.d1 * sourceScale, d2 = row.d2 * sourceScale;
  return { ...row, d0, d1, d2, e0: d0 * 0.98, e1: d1 * 1.02, e2: d2 * 0.985 };
});
export function integrate(data, key, { zeroLimitKnown = false } = {}) {
  if (data.some(row => !Number.isFinite(row[key]))) return { lambda: null, wlog: null };
  if (data[0]?.f === 0 && (!zeroLimitKnown || data[0][key] !== 0)) return { lambda: null, wlog: null };
  let lambda = 0, moment = 0;
  for (let i = 1; i < data.length; i++) {
    const a = data[i - 1], b = data[i];
    if (!(a.f >= 0 && b.f > a.f)) return { lambda: null, wlog: null };
    const dx = b.f - a.f, u = a.f === 0 ? 0 : a[key] / a.f, v = b[key] / b.f;
    lambda += dx * (u + v);
    moment += dx * ((a.f === 0 ? 0 : u * Math.log(a.f)) + v * Math.log(b.f));
  }
  return { lambda, wlog: lambda > 0 ? Math.exp(moment / lambda) * 47.99243073366221 : null };
}
export const integral = integrate(rows, 'a', { zeroLimitKnown: true });
export const reference = integrate(rows, 'original', { zeroLimitKnown: true });
