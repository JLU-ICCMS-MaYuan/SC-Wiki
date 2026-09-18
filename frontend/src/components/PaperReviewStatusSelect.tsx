import { FormControl, InputLabel, MenuItem, Select } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { PAPER_REVIEW_OPTIONS } from '../lib/paperReview'

export default function PaperReviewStatusSelect({ id, value, onChange, disabled = false }: {
  id: string
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}) {
  const { t } = useLanguage()
  return (
    <FormControl fullWidth size="small" disabled={disabled}>
      <InputLabel id={`${id}-label`}>{t('admin.reviewResult')}</InputLabel>
      <Select id={id} labelId={`${id}-label`} value={value} label={t('admin.reviewResult')}
        onChange={event => onChange(event.target.value)}>
        {PAPER_REVIEW_OPTIONS.map(option => <MenuItem key={option.value} value={option.value}>{t(option.label)}</MenuItem>)}
      </Select>
    </FormControl>
  )
}
