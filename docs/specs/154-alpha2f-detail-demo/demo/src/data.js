// 合成的已知谱：只用于交互和数值显示验证，不对应任何材料测量。
const gaussian = (x, center, width) => Math.exp(-(((x - center) / width) ** 2));
export const rows = Array.from({ length: 279 }, (_, i) => {
  const f = 0.5 + i * 0.25;
  const original = 0.32 * gaussian(f, 11, 4) + 1.05 * gaussian(f, 28, 5) + 0.7 * gaussian(f, 45, 9) + 0.28 * gaussian(f, 59, 3);
  const a = original * (0.975 + 0.08 * (f / 70 - 0.5) + 0.013 * Math.sin(f * 1.8));
  const d0 = 0.85 * gaussian(f, 7, 3) + 0.18 * gaussian(f, 18, 3);
  const d1 = 0.65 * gaussian(f, 15, 4) + 0.22 * gaussian(f, 24, 3);
  const d2 = 0.9 * gaussian(f, 38, 8) + 0.65 * gaussian(f, 54, 6);
  return { id: i + 1, f, original, a, diff: a - original, d0, d1, d2,
    e0: d0 * 0.98, e1: d1 * 1.02, e2: f >= 32.5 && f <= 34 ? null : d2 * 0.985 };
});
export function integrate(data, key) {
  let lambda = 0, moment = 0;
  for (let i = 1; i < data.length; i++) {
    const a = data[i - 1], b = data[i];
    if (!(a.f > 0 && b.f > a.f) || a[key] == null || b[key] == null) continue;
    const dx = b.f - a.f, u = a[key] / a.f, v = b[key] / b.f;
    lambda += dx * (u + v);
    moment += dx * (u * Math.log(a.f) + v * Math.log(b.f));
  }
  return { lambda, wlog: lambda > 0 ? Math.exp(moment / lambda) * 47.99243073366221 : null };
}
export const integral = integrate(rows, 'a');
export const reference = integrate(rows, 'original');
