import React, { useState } from 'react'
import { Box, Chip, Collapse, Typography } from '@mui/material'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import { EvidenceRecord } from './EvidenceWorkflow'

export default function EvidenceIssueMarker({ record }: { record: EvidenceRecord }) {
  const [open, setOpen] = useState(false)
  return <Box sx={{ mt: 1 }}>
    <Chip size="small" color={record.status === 'missing' ? 'error' : 'warning'} icon={<WarningAmberIcon />} label="证据核对有问题" onClick={() => setOpen(value => !value)} />
    <Collapse in={open}>
      <Box sx={{ mt: 1, p: 1.5, borderLeft: 3, borderColor: record.status === 'missing' ? 'error.main' : 'warning.main', bgcolor: 'action.hover' }}>
        <Typography variant="body2"><strong>问题：</strong>{record.reason}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}><strong>建议：</strong>{record.suggestion || '请检查该物性类型、数值、单位和实验条件，并确认原文是否直接支持。'}</Typography>
        {record.evidences.length > 0 && <Box component="details" sx={{ mt: 1 }}>
          <Box component="summary" sx={{ cursor: 'pointer' }}>系统找到的 evidence</Box>
          {record.evidences.map((e, i) => <Typography key={i} variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>{e.page_start ? `第 ${e.page_start}${e.page_end && e.page_end !== e.page_start ? `–${e.page_end}` : ''} 页：` : ''}{e.quote || e.content}</Typography>)}
        </Box>}
      </Box>
    </Collapse>
  </Box>
}
