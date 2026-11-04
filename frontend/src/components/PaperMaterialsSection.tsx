import { createContext, useContext, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Box, Button, IconButton, Paper, Typography } from '@mui/material'
import { ChevronLeft, ChevronRight } from '@mui/icons-material'
import { useLanguage } from '../context/LanguageContext'
import { locateMaterialState, type MaterialSummaryState } from '../lib/paperMaterials'
import { materialStateSummary } from '../lib/materialStateSummary'
import { toTextList } from '../lib/paperTextLists'

interface Props { states: MaterialSummaryState[]; historicalMaterials?: unknown }

const OutlineSlot = createContext<HTMLElement | null | undefined>(undefined)

/** 外层工作区统一分栏；嵌套编辑器复用外层栏位，不重复留宽。 */
export function MaterialOutlineLayout({ children }: { children: ReactNode }) {
  const parent = useContext(OutlineSlot)
  if (parent !== undefined) return children
  return <OutlineColumns>{children}</OutlineColumns>
}

function OutlineColumns({ children }: { children: ReactNode }) {
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  return <OutlineSlot.Provider value={slot}>
    <Box data-material-outline-layout sx={{
      display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: '4px', alignItems: 'start', minWidth: 0,
      '&:has([data-material-outline-panel])': {
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'minmax(0, 1fr) 40px' },
        '& > [data-material-outline-content]': { gridRow: { xs: 2, lg: 1 } },
        '& > [data-material-outline-slot]': { display: 'block' },
      },
      '&:has([data-material-outline-panel="expanded"])': {
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'minmax(0, 1fr) 240px' },
      },
    }}>
      <Box data-material-outline-content sx={{ minWidth: 0, gridColumn: 1 }}>{children}</Box>
      <Box ref={setSlot} data-material-outline-slot sx={{
        display: 'contents', minWidth: 0, gridColumn: { xs: 1, lg: 2 }, gridRow: 1,
        position: { xs: 'static', lg: 'sticky' }, top: 4, alignSelf: 'start',
      }} />
    </Box>
  </OutlineSlot.Provider>
}

/** 大纲只读宿主当前值；展开和定位不进入科学数据保存链。 */
export default function PaperMaterialsSection({ states, historicalMaterials }: Props) {
  const { t, lang } = useLanguage()
  const [expanded, setExpanded] = useState(true)
  const anchor = useRef<HTMLDivElement>(null)
  const slot = useContext(OutlineSlot)
  const title = lang === 'zh' ? '研究材料大纲' : 'Material outline'
  const action = lang === 'zh' ? (expanded ? '收起研究材料大纲' : '展开研究材料大纲')
    : (expanded ? 'Collapse material outline' : 'Expand material outline')
  const panel = <Paper component="nav" aria-label={title} data-material-outline-panel={expanded ? 'expanded' : 'collapsed'} variant="outlined" sx={{
      display: 'flex', flexDirection: 'column', borderRadius: 2, overflow: 'hidden',
      height: expanded ? { xs: 'min(360px, 50dvh)', lg: 'calc(100dvh - 8px)' } : 'auto',
    }}>
      <Box sx={{ display: 'flex', flexShrink: 0, alignItems: 'center', justifyContent: 'space-between', p: 0.5 }}>
        {expanded && <Typography variant="subtitle2" sx={{ pl: 1 }}>{t('upload.researchMaterialsTitle')}</Typography>}
        <IconButton component="a" role="button" size="small" aria-label={action} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          {expanded ? <ChevronRight /> : <ChevronLeft />}
        </IconButton>
      </Box>
      {expanded && <Box data-material-outline-list data-issue-field="paper.research_materials" sx={{ flex: 1, minHeight: 0, overflowY: 'auto', p: 1 }}>
        {states.map((state, index) => <Button component="a" role="button" key={state.state_key || index} fullWidth size="small"
          sx={{ justifyContent: 'flex-start', textAlign: 'left', fontSize: '0.75rem', overflowWrap: 'anywhere', mb: 0.5 }}
          onClick={() => { if (anchor.current) locateMaterialState(anchor.current, index, state.state_key) }}>
          {'#' + (index + 1) + ' · ' + materialStateSummary({ ...state, material: state.material ?? state.superconductor?.chemical_formula })}
        </Button>)}
        {!states.length && <Typography variant="body2">{toTextList(historicalMaterials).join(t('upload.listSeparator')) || t('common.notProvided')}</Typography>}
      </Box>}
    </Paper>
  return <Box ref={anchor} data-material-outline-expanded={expanded ? 'true' : 'false'} sx={{ display: 'contents' }}>
    {slot ? createPortal(panel, slot) : slot === undefined ? panel : null}
  </Box>
}
