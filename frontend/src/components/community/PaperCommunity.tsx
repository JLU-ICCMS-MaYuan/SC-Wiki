import React from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { Box, Chip, Stack, Typography } from '@mui/material'
import { useLanguage } from '../../context/LanguageContext'
import CommentPanel from './CommentPanel'

interface PaperContext { id: number; chemical_systems?: Array<{ system_key?: string }>; material_states?: Array<{ system_key?: string; superconductor?: { chemical_system?: { system_key?: string } } }> }
export default function PaperCommunity({ paper }: { paper: PaperContext }) {
  const { t } = useLanguage()
  const keys = [...new Set([...(paper.chemical_systems || []).map(s => s.system_key), ...(paper.material_states || []).map(s => s.system_key || s.superconductor?.chemical_system?.system_key)].filter((key): key is string => Boolean(key)))]
  return <Box sx={{ mt: 4 }}>
    <Typography variant="h2">{t('community.paperComments')}</Typography>
    {keys.length > 0 && <Stack direction="row" flexWrap="wrap" gap={1} sx={{ my: 2 }}>{keys.map(key => <Chip key={key} label={t('community.systemDiscussion', { key })} component={RouterLink} to={`/systems/${encodeURIComponent(key)}`} clickable />)}</Stack>}
    <CommentPanel key={`comments-${paper.id}`} target={{ paper_id: paper.id }} />
  </Box>
}
