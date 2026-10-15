import { useLayoutEffect, useRef, useState } from 'react'
import { Box, TextField, type TextFieldProps } from '@mui/material'

/** 用与输入框相同的字体测量文本；长内容只扩展本行，不压缩相邻字段。 */
export default function AutoGrowingTextField({ value, label, sx, minFieldWidth = 110, ...props }: TextFieldProps & { minFieldWidth?: number }) {
  const measure = useRef<HTMLSpanElement>(null)
  const [width, setWidth] = useState(minFieldWidth)
  useLayoutEffect(() => {
    setWidth(Math.max(minFieldWidth, Math.ceil(measure.current?.getBoundingClientRect().width || 0) + 36))
  }, [value, label, minFieldWidth])
  return <Box sx={{ position: 'relative', flex: '0 0 auto', width }} data-auto-growing-field>
    <Box component="span" ref={measure} aria-hidden sx={{ position: 'absolute', visibility: 'hidden', whiteSpace: 'pre', fontFamily: 'inherit', fontSize: '1rem', fontWeight: 400, width: 'max-content', pointerEvents: 'none' }}>{String(value ?? '')}</Box>
    <TextField {...props} size="small" value={value ?? ''} label={label} sx={{ width: '100%', ...sx }} />
  </Box>
}
