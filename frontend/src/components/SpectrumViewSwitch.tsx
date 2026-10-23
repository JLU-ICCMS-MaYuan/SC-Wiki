import { Box, Button } from '@mui/material'

const options = [['source', '仅原图'], ['data', '仅提取数据'], ['overlay', '原图与数据叠加']]

export default function SpectrumViewSwitch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const index = Math.max(0, options.findIndex(([key]) => key === value))
  return <Box role="group" aria-label="结果显示方式" sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.45fr', position: 'relative', bgcolor: '#e8e8ed', borderRadius: '20px', p: .5, width: '100%', maxWidth: 480, isolation: 'isolate' }}>
    <Box data-testid="spectrum-view-indicator" aria-hidden="true" sx={{ position: 'absolute', top: 4, bottom: 4, left: 4,
      width: index === 2 ? 'calc((100% - 8px) * 1.45 / 3.45)' : 'calc((100% - 8px) / 3.45)',
      transform: index === 0 ? 'translateX(0)' : index === 1 ? 'translateX(100%)' : 'translateX(calc(200% / 1.45))',
      bgcolor: 'primary.main', borderRadius: '16px', zIndex: -1, transition: 'transform 240ms ease, width 240ms ease',
      '@media (prefers-reduced-motion: reduce)': { transition: 'none' } }} />
    {options.map(([key, label]) => <Button key={key} aria-pressed={value === key} onClick={() => onChange(key)} disableRipple sx={{ minWidth: 0, px: .8, py: .8, borderRadius: '16px', minHeight: 38, whiteSpace: 'nowrap', fontSize: { xs: 11, sm: 12 }, color: value === key ? '#fff' : 'text.primary', transition: 'color 160ms ease', '&:hover': { bgcolor: value === key ? 'transparent' : 'action.hover' } }}>{label}</Button>)}
  </Box>
}
