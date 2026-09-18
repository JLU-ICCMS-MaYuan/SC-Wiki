import type { ReactNode } from 'react'
import { Box } from '@mui/material'

interface PaperMetadataRowProps {
  journal: ReactNode
  year: ReactNode
  issueNumber: ReactNode
  volume: ReactNode
  pages: ReactNode
  doi: ReactNode
}

export default function PaperMetadataRow(fields: PaperMetadataRowProps) {
  return (
    <Box sx={{ minWidth: 0, overflowX: 'auto', gridColumn: '1 / -1', py: 1 }}>
      <Box data-testid="paper-metadata-row" sx={{
        display: 'grid', minWidth: 1080,
        gridTemplateColumns: 'minmax(0, 4fr) repeat(4, minmax(0, 1fr)) minmax(0, 4fr)',
        gap: 1.5, alignItems: 'start', '& > *': { minWidth: 0 },
      }}>
        {fields.journal}
        {fields.year}
        {fields.issueNumber}
        {fields.volume}
        {fields.pages}
        {fields.doi}
      </Box>
    </Box>
  )
}
