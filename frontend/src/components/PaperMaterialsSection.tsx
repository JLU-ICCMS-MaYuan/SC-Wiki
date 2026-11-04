import { useLayoutEffect, useRef, useState } from 'react'
import { Box, Button, GlobalStyles, IconButton, Paper, Typography } from '@mui/material'
import { ChevronLeft, ChevronRight } from '@mui/icons-material'
import { useLanguage } from '../context/LanguageContext'
import { locateMaterialState, type MaterialSummaryState } from '../lib/paperMaterials'
import { materialStateSummary } from '../lib/materialStateSummary'
import { toTextList } from '../lib/paperTextLists'

interface Props { states: MaterialSummaryState[]; historicalMaterials?: unknown }

/** 大纲只读宿主当前值；展开和定位不进入科学数据保存链。 */
export default function PaperMaterialsSection({ states, historicalMaterials }: Props) {
  const { t, lang } = useLanguage()
  const [expanded, setExpanded] = useState(true)
  const anchor = useRef<HTMLDivElement>(null)
  const outline = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const host = anchor.current?.closest<HTMLElement>('[data-evidence-scope], [data-paper-detail]')
    const panel = outline.current
    if (!host || !panel || !expanded) return
    let previousBounds = ''
    const measure = () => {
      if (window.innerWidth < 1200) return
      const bounds = host.getBoundingClientRect(), left = panel.getBoundingClientRect().left
      if (!bounds.width) return
      const identity = `${bounds.width}:${bounds.right}:${left}`
      if (identity === previousBounds) return
      previousBounds = identity
      // 各宿主外层留白不同；仅在横向边界变化时测量首张卡片，不扫描表单字段。
      const card = host.querySelector<HTMLElement>(host.hasAttribute('data-paper-detail') ? '.MuiCard-root' : '[data-material-state-index]')
      const reserved = parseFloat(getComputedStyle(host).paddingRight) || 0
      const cardBounds = card?.getBoundingClientRect()
      const right = cardBounds?.width ? cardBounds.right : bounds.right - reserved
      host.style.setProperty('--material-outline-space', `${Math.max(0, reserved + 4 - (left - right))}px`)
    }
    measure()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(host, { box: 'border-box' })
    observer?.observe(panel, { box: 'border-box' })
    window.addEventListener('resize', measure)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', measure)
      host.style.removeProperty('--material-outline-space')
    }
  }, [expanded, states.length])
  const title = lang === 'zh' ? '研究材料大纲' : 'Material outline'
  const action = lang === 'zh' ? (expanded ? '收起研究材料大纲' : '展开研究材料大纲')
    : (expanded ? 'Collapse material outline' : 'Expand material outline')
  return <Box ref={anchor} data-material-outline-expanded={expanded ? 'true' : 'false'}>
    <GlobalStyles styles={{
      '@media (min-width: 1200px)': {
        '[data-evidence-scope="upload-editor"]:has([data-material-outline-expanded="true"]), [data-evidence-scope="paper-edit"]:has([data-material-outline-expanded="true"]), [data-paper-detail]:has([data-material-outline-expanded="true"])': { paddingRight: 'var(--material-outline-space, 248px)' },
      },
    }} />
    <Paper ref={outline} component="nav" aria-label={title} variant="outlined" sx={{
      position: 'fixed', top: 4, bottom: expanded ? 4 : undefined, right: 12, width: expanded ? { xs: 'min(240px, 80vw)', lg: 240 } : 40,
      display: 'flex', flexDirection: 'column', zIndex: 100, borderRadius: 2, maxHeight: 'calc(100dvh - 8px)', overflow: 'hidden',
    }}>
      <Box sx={{ display: 'flex', flexShrink: 0, alignItems: 'center', justifyContent: 'space-between', p: 0.5 }}>
        {expanded && <Typography variant="subtitle2" sx={{ pl: 1 }}>{t('upload.researchMaterialsTitle')}</Typography>}
        <IconButton component="a" role="button" size="small" aria-label={action} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          {expanded ? <ChevronRight /> : <ChevronLeft />}
        </IconButton>
      </Box>
      {expanded && <Box data-issue-field="paper.research_materials" sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
        {states.map((state, index) => <Button component="a" role="button" key={state.state_key || index} fullWidth size="small"
          sx={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: '0.75rem', overflowWrap: 'anywhere', mb: 0.5 }}
          onClick={() => { if (anchor.current) locateMaterialState(anchor.current, index, state.state_key) }}>
          {'#' + (index + 1) + ' · ' + materialStateSummary({ ...state, material: state.material ?? state.superconductor?.chemical_formula })}
        </Button>)}
        {!states.length && <Typography variant="body2">{toTextList(historicalMaterials).join(t('upload.listSeparator')) || t('common.notProvided')}</Typography>}
      </Box>}
    </Paper>
  </Box>
}
