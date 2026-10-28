import { Alert, Box, Button, Typography } from '@mui/material'
import EvidenceReadableValue from './EvidenceReadableValue'
import { EvidenceRegion } from './EvidenceRegion'
import type { EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'
import { useLanguage } from '../context/LanguageContext'

export interface FieldCandidate {
  id?: string; token?: string; preparation_id?: string; values: Record<string, unknown>; explanation: string
  evidences: EvidenceSource[]; can_apply: boolean; historical: boolean; origin?: string
}

export default function FieldAICandidate({ candidate, target, loading, error, disabled, busy, retrying, onApply }: {
  candidate?: FieldCandidate | null; target?: EvidenceTarget; loading?: boolean; error?: string
  disabled: boolean; busy: boolean; retrying: boolean; onApply: () => void
}) {
  const { t } = useLanguage()
  return <Box component="section" aria-label={t('evidence.candidateTitle')} data-evidence-ignore
    sx={{ mt: 3, p: 2, border: '1px solid', borderColor: 'primary.main', borderRadius: 2, display: 'grid', gap: 1.5 }}>
    <Typography variant="subtitle1" fontWeight={700}>{t('evidence.candidateTitle')}</Typography>
    {error ? <Alert severity="error">{error}</Alert> : loading ? <Typography role="status">{t('evidence.candidateLoading')}</Typography>
      : candidate ? <>
        {candidate.historical && <Alert severity="info">{t('evidence.candidateHistorical')}</Alert>}
        <EvidenceReadableValue value={Object.keys(candidate.values).length === 1 && '' in candidate.values ? candidate.values[''] : candidate.values} />
        {candidate.explanation && <><Typography fontWeight={600}>{t('evidence.candidateReason')}</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{candidate.explanation}</Typography></>}
        {candidate.evidences.map((source, index) => <EvidenceRegion key={index} target={target} source={source} />)}
        <Typography variant="body2" color="text.secondary">{t('evidence.candidateConsent')}</Typography>
      </> : <Typography color="text.secondary">{t('evidence.candidateEmpty')}</Typography>}
    {(candidate || retrying) && <Button variant="contained" disabled={disabled || busy || (!retrying && !candidate?.can_apply)} onClick={onApply}>
      {busy ? t('evidence.candidateApplying') : retrying ? t('evidence.candidateRetry') : t('evidence.candidateApply')}
    </Button>}
  </Box>
}
