import React from 'react'

// 理想迈斯纳态的定性图：连续外场线避开整个圆片截面，不是三维场求解。
export default function MagneticField() {
  return <g className="sc-magnetic-field" pointerEvents="none" aria-hidden="true">
    <g className="sc-field-lines" fill="none" stroke="#238ca5" strokeWidth="1.8" opacity=".88" markerEnd="url(#sc-field-arrow)">
      {[-1, 1].flatMap(side => Array.from({ length: 4 }, (_, i) => {
        const start = side * (8 + 18 * i)
        const bend = side * (58 + 14 * i)
        return <path key={`${side}-${i}`} d={`M${start} 78 C${start} 55 ${bend} 50 ${bend} 11 S${bend} -34 ${start} -65`} />
      }))}
    </g>
    {/* 反向磁矩对应的表面屏蔽电流，与外场箭头使用不同颜色。 */}
    <g className="sc-screening-current" fill="none" stroke="#9868bf" strokeWidth="1.7">
      <path d="M-45-5 A45 23 0 0 1 45-5" strokeDasharray="3 3" opacity=".65" />
      <path d="M45-5 A45 23 0 0 1 -45-5" markerEnd="url(#sc-current-arrow)" opacity=".95" />
    </g>
  </g>
}
