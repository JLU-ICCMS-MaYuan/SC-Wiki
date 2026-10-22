import React, { useLayoutEffect, useRef, useState } from 'react'
import { Box, Chip } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'

export interface NewsClassification {
  paper_type?: 'experimental' | 'theoretical' | 'review' | null
  theoretical_subtype?: 'calculation' | 'method' | 'theory' | null
  material_families?: { id: number; name_zh: string; name_en: string }[]
}

/** 卡片仅折叠溢出的家族，详情展示所有标签；按实际宽度而非固定数量裁剪。 */
export default function NewsClassificationLabels({ item, expanded = false }: { item: NewsClassification; expanded?: boolean }) {
  const { dict, lang, t } = useLanguage()
  const container = useRef<HTMLDivElement>(null)
  const measurements = useRef<HTMLDivElement>(null)
  const families = (item.material_families || []).map(family => ({
    id: family.id, label: lang === 'en' ? family.name_en || family.name_zh : family.name_zh,
  }))
  const fixed = [
    item.paper_type ? dict.enums.paperType[item.paper_type] : '',
    item.paper_type === 'theoretical' && item.theoretical_subtype ? dict.enums.theoreticalSubtype[item.theoretical_subtype] : '',
  ].filter(Boolean)
  const [visible, setVisible] = useState(0)
  const signature = JSON.stringify([fixed, families])
  useLayoutEffect(() => {
    if (expanded) return
    const measure = () => {
      const width = container.current?.getBoundingClientRect().width || 0
      const children = measurements.current?.children
      if (!children || !width) return
      const widths = Array.from(children).map(child => child.getBoundingClientRect().width)
      const used = widths.slice(0, fixed.length).reduce((total, value) => total + Math.min(value, width * 0.4) + 4, 0)
      let available = width - used
      const familyWidths = widths.slice(fixed.length, -1)
      if (familyWidths.reduce((sum, value) => sum + value + 4, 0) <= available) {
        setVisible(families.length)
        return
      }
      available -= widths[widths.length - 1] + 4
      let count = 0
      for (const value of familyWidths) {
        if (value + 4 > available) break
        available -= value + 4
        count++
      }
      setVisible(count)
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    if (container.current) observer?.observe(container.current)
    return () => observer?.disconnect()
  }, [signature, expanded]) // 标签及语言变化后重新测量。

  if (!fixed.length && !families.length) return null
  const shown = expanded ? families : families.slice(0, visible)
  const hidden = families.length - shown.length
  const chip = { height: 22, fontSize: 11, maxWidth: expanded ? '100%' : 180 }
  return <Box ref={container} data-testid="news-classification" sx={{ position: 'relative', minWidth: 0, my: 0.5 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: expanded ? 'wrap' : 'nowrap', overflow: 'hidden', minHeight: 22 }}>
      {fixed.map(label => <Chip key={label} label={label} title={label} size="small" variant="outlined" sx={{ ...chip, minWidth: 0, maxWidth: expanded ? '100%' : '40%' }} />)}
      {shown.map(family => <Chip key={family.id} label={family.label} title={family.label} size="small" sx={{ ...chip, flexShrink: 0 }} />)}
      {hidden > 0 && <Chip label={`+${hidden}`} title={t('news.moreFamilies', { count: hidden })} aria-label={t('news.moreFamilies', { count: hidden })} size="small" sx={{ ...chip, flexShrink: 0 }} />}
    </Box>
    {!expanded && <Box ref={measurements} aria-hidden="true" sx={{ position: 'absolute', visibility: 'hidden', pointerEvents: 'none', display: 'flex', gap: '4px', width: 'max-content', height: 0, overflow: 'hidden' }}>
      {fixed.map(label => <Chip key={label} label={label} size="small" variant="outlined" sx={chip} />)}
      {families.map(family => <Chip key={family.id} label={family.label} size="small" sx={chip} />)}
      <Chip label={`+${families.length}`} size="small" sx={chip} />
    </Box>}
  </Box>
}
