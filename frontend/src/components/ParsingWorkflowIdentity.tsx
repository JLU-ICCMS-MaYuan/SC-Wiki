import React from 'react'
import { Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import type { ParsingWorkflowBinding } from '../lib/paperProcessing'

const ParsingWorkflowIdentity: React.FC<{ binding?: ParsingWorkflowBinding }> = ({ binding }) => {
  const { t } = useLanguage()
  if (!binding) return null
  const name = binding.workflow_key === 'conventional-theory-calculation'
    ? t('upload.workflowConventional') : binding.workflow_key
  return <Typography variant="caption" color="text.secondary" data-parsing-workflow={binding.workflow_key}>
    {t('upload.workflowIdentity', { name, version: binding.form_version })}
  </Typography>
}

export default React.memo(ParsingWorkflowIdentity)
