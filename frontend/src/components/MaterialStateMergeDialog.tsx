import React, { useState } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, FormControl, InputLabel, MenuItem, Select, TextField, Typography } from '@mui/material'
import type { MaterialStateSnapshot } from '../lib/splitMaterialState'
import { materialLabel } from '../lib/materialIdentity'
import { useLanguage } from '../context/LanguageContext'

export default function MaterialStateMergeDialog({ source, targets, readOnly, onCancel, onConfirm }: {
  source: MaterialStateSnapshot
  targets: MaterialStateSnapshot[]
  readOnly: boolean
  onCancel: () => void
  onConfirm: (target: MaterialStateSnapshot, note: string) => boolean
}) {
  const { t } = useLanguage()
  const [targetKey, setTargetKey] = useState(targets.length === 1 ? targets[0].state.state_key! : '')
  const [note, setNote] = useState('')
  const [stale, setStale] = useState(false)
  const target = targets.find(item => item.state.state_key === targetKey)
  const state = source.state
  return <Dialog open fullWidth maxWidth="sm" onClose={onCancel} aria-labelledby="merge-material-state-title">
    <DialogTitle id="merge-material-state-title">{t('upload.mergeStructureAndProperties')}</DialogTitle>
    <DialogContent>
      <Alert severity="info" sx={{ mb: 2 }}>{t('upload.mergeSourceNotice')}</Alert>
      {stale && <Alert severity="warning" sx={{ mb: 2 }}>{t('upload.splitStale')}</Alert>}
      {!targets.length && <Alert severity="info" sx={{ mb: 2 }}>{t('upload.noMergeTarget')}</Alert>}
      <FormControl fullWidth><InputLabel id="merge-state-target-label">{t('upload.mergeTarget')}</InputLabel>
        <Select labelId="merge-state-target-label" label={t('upload.mergeTarget')} value={targetKey} disabled={readOnly}
          onChange={event => setTargetKey(event.target.value)}>
          {targets.map(item => <MenuItem key={item.state.state_key} value={item.state.state_key}>
            {materialLabel(item.state)} · {item.state.pressure_value_gpa} GPa · {item.state.reported_space_group_symbol || '—'}
          </MenuItem>)}
        </Select>
      </FormControl>
      {target && <Box sx={{ my: 2 }}>
        <Typography fontWeight={700}>{t('upload.mergeResult')}</Typography>
        <Typography>{materialLabel(target.state)} · {state.pressure_value_gpa} GPa · {state.reported_space_group_symbol}</Typography>
        <Typography>{t('upload.splitRecordCount', { count: target.state.property_modules!.reduce((n, m) => n + m.records.length, 0) })}</Typography>
      </Box>}
      {Boolean(state.structure?.user_note) && <Typography sx={{ whiteSpace: 'pre-wrap', my: 1 }}>{String(state.structure?.user_note)}</Typography>}
      <TextField fullWidth multiline minRows={3} label={t('upload.additionalStructureNote')} value={note} disabled={readOnly}
        onChange={event => setNote(event.target.value)} />
    </DialogContent>
    <DialogActions><Button onClick={onCancel}>{t('common.cancel')}</Button>
      <Button variant="contained" disabled={readOnly || !target || stale} onClick={() => {
        if (target && !onConfirm(target, note)) setStale(true)
      }}>{t('upload.confirmStateMerge')}</Button>
    </DialogActions>
  </Dialog>
}
