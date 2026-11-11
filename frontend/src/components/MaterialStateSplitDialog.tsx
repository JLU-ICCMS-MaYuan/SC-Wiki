import React, { useState } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from '@mui/material'
import type { MaterialStateSplitPreview } from '../lib/splitMaterialState'
import { materialLabel } from '../lib/materialIdentity'
import { useLanguage } from '../context/LanguageContext'

export default function MaterialStateSplitDialog({ preview, groups, readOnly, onCancel, onConfirm }: {
  preview: MaterialStateSplitPreview
  groups: Array<{ number: number; symbol: string }>
  readOnly: boolean
  onCancel: () => void
  onConfirm: (number: number) => boolean
}) {
  const { t } = useLanguage()
  const [number, setNumber] = useState(String(preview.state.reported_space_group_number || ''))
  const [stale, setStale] = useState(false)
  const selected = groups.find(group => group.number === Number(number))
  const source = preview.state
  const count = (source.property_modules || []).reduce((total, module) => total + module.records.length, 0)
  return <Dialog open fullWidth maxWidth="sm" onClose={onCancel} aria-labelledby="split-material-state-title">
    <DialogTitle id="split-material-state-title">{t('upload.splitStructureAndProperties')}</DialogTitle>
    <DialogContent>
      <Alert severity="info" sx={{ mb: 2 }}>{t('upload.splitSourceNotice')}</Alert>
      {stale && <Alert severity="warning" sx={{ mb: 2 }}>{t('upload.splitStale')}</Alert>}
      <TextField label={t('upload.propertyStateGroupNumber')} type="number" value={number} fullWidth
        disabled={readOnly} slotProps={{ htmlInput: { min: 1, max: 230 } }}
        onChange={event => setNumber(event.target.value)} helperText={selected?.symbol || '—'} />
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mt: 2 }}>
        <Box><Typography fontWeight={700}>{t('upload.retainedPropertyState')}</Typography>
          <Typography>{materialLabel(source)} · {source.pressure_value_gpa ?? '—'} GPa · {selected?.symbol || '—'}</Typography>
          <Typography>{t('upload.splitRecordCount', { count })}</Typography>
        </Box>
        <Box><Typography fontWeight={700}>{t('upload.newStructureState')}</Typography>
          <Typography>{materialLabel(source)} · {source.pressure_value_gpa ?? '—'} GPa · {source.reported_space_group_symbol || '—'}</Typography>
          <Typography>{t('upload.splitOriginalStructure')}</Typography>
        </Box>
      </Box>
    </DialogContent>
    <DialogActions><Button onClick={onCancel}>{t('common.cancel')}</Button>
      <Button variant="contained" disabled={readOnly || !selected || stale} onClick={() => {
        if (selected && !onConfirm(selected.number)) setStale(true)
      }}>{t('upload.confirmStateSplit')}</Button>
    </DialogActions>
  </Dialog>
}
