import { useRef, useState } from 'react'
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
  const title = lang === 'zh' ? '研究材料大纲' : 'Material outline'
  const action = lang === 'zh' ? (expanded ? '收起研究材料大纲' : '展开研究材料大纲')
    : (expanded ? 'Collapse material outline' : 'Expand material outline')
  return <Box ref={anchor} data-material-outline-expanded={expanded ? 'true' : 'false'}>
    <GlobalStyles styles={{
      '@media (min-width: 1200px)': {
        '[data-evidence-scope="upload-editor"]:has([data-material-outline-expanded="true"]), [data-evidence-scope="paper-edit"]:has([data-material-outline-expanded="true"]), [data-paper-detail]:has([data-material-outline-expanded="true"])': { paddingRight: 256 },
      },
    }} />
    <Paper component="nav" aria-label={title} variant="outlined" sx={{
      position: 'fixed', top: 100, right: 12, width: expanded ? { xs: 'min(240px, 80vw)', lg: 240 } : 40,
      zIndex: 100, borderRadius: 2, maxHeight: 'calc(100dvh - 120px)', overflow: 'hidden',
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 0.5 }}>
        {expanded && <Typography variant="subtitle2" sx={{ pl: 1 }}>{t('upload.researchMaterialsTitle')}</Typography>}
        <IconButton component="a" role="button" size="small" aria-label={action} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
          {expanded ? <ChevronRight /> : <ChevronLeft />}
        </IconButton>
      </Box>
      {expanded && <Box data-issue-field="paper.research_materials" sx={{ maxHeight: 'calc(100dvh - 170px)', overflowY: 'auto', p: 1 }}>
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
