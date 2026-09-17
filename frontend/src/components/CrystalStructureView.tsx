import { useCallback, useState } from 'react'
import { Box, Table, TableBody, TableCell, TableHead, TableRow, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import StructureViewer3D from './StructureViewer3D'
import { type CrystalStructureData, crystalNumber } from '../lib/crystalStructure'
import { useLanguage } from '../context/LanguageContext'
import { viewerFormat } from '../lib/paperDetailView'

export default function CrystalStructureView({ data, format = 'cif' }: { data: string; format?: string }) {
  const { t } = useLanguage()
  const [coordinates, setCoordinates] = useState<'fractional' | 'cartesian'>('fractional')
  const [parsed, setParsed] = useState<{ source: string; value: CrystalStructureData | null } | null>(null)
  const source = `${format}\n${data}`
  const onParsed = useCallback((value: CrystalStructureData | null) => setParsed({ source, value }), [source])
  // 异步解析期间不显示上一个文件/晶胞的数据。
  const value = parsed?.source === source ? parsed.value : null
  const tableSx = { minWidth: 280, '& th, & td': { px: 0.75, py: 0.75, fontSize: 12, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }, '& th:first-of-type': { width: '22%' } }

  return <Box data-crystal-layout sx={{ containerType: 'inline-size', width: '100%', minWidth: 0 }}>
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr', gap: 2.5, '@container (min-width: 740px)': { gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)' } }}>
      <Box data-crystal-model sx={{ minWidth: 0, height: 280, '@container (min-width: 740px)': { height: 400 } }}>
        <StructureViewer3D data={data} format={viewerFormat(format)} height="100%" onStructureData={onParsed} controls showLegend={false} />
      </Box>
      <Box data-crystal-data tabIndex={0} role="region" aria-label={t('upload.crystalParamsTitle')} sx={{ minWidth: 0, height: 400, overflow: 'auto', overscrollBehavior: 'contain', containerType: 'inline-size' }}>
        {!value ? <Typography variant="body2" color="text.secondary">{t(parsed?.source === source ? 'upload.structureDataUnavailable' : 'common.loading')}</Typography> : <>
          <Typography variant="subtitle2" fontWeight={700}>{t('upload.crystalParamsTitle')}</Typography>
          <Typography variant="caption" color="text.secondary">{t('upload.volumeLine', { volume: `${crystalNumber(value.volume)} Å³` })}</Typography>
          <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1.25, mt: 1.5, mb: 2, '@container (max-width: 300px)': { gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }, '@container (max-width: 190px)': { gridTemplateColumns: 'minmax(0, 1fr)' } }}>
            {value.parameters.map((parameter, index) => <Box key={index}>
              <Typography component="dt" variant="caption" color="text.secondary">{['a', 'b', 'c', 'α', 'β', 'γ'][index]} ({index < 3 ? 'Å' : '°'})</Typography>
              <Typography component="dd" variant="body2" sx={{ m: 0, fontVariantNumeric: 'tabular-nums' }}>{crystalNumber(parameter)}</Typography>
            </Box>)}
          </Box>
          <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 1.5 }}>
            <Typography variant="subtitle2" fontWeight={700}>{t('upload.latticeMatrixTitle')}</Typography>
            <Typography variant="caption" color="text.secondary">{t('upload.latticeRows')}</Typography>
            <Box sx={{ overflowX: 'auto' }} tabIndex={0} role="region" aria-label={t('upload.latticeMatrixTitle')}>
            <Table size="small" aria-label={t('upload.latticeMatrixTitle')} sx={tableSx}>
              <TableHead><TableRow><TableCell>{t('upload.latticeVector')}</TableCell>{['x', 'y', 'z'].map(axis => <TableCell key={axis} align="right">{axis}</TableCell>)}</TableRow></TableHead>
              <TableBody>{value.lattice.map((row, index) => <TableRow key={index}><TableCell component="th" scope="row">{['a', 'b', 'c'][index]}</TableCell>{row.map((number, i) => <TableCell key={i} align="right">{crystalNumber(number)}</TableCell>)}</TableRow>)}</TableBody>
            </Table>
            </Box>
          </Box>
          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1, mb: 1 }}>
              <Typography variant="subtitle2" fontWeight={700}>{t('upload.atomicPositionsTitle', { count: value.atoms.length })}</Typography>
              <ToggleButtonGroup exclusive size="small" value={coordinates} onChange={(_, next) => { if (next) setCoordinates(next) }} aria-label={t('upload.coordinateType')}>
                <ToggleButton value="fractional">{t('upload.fractionalCoordinates')}</ToggleButton>
                <ToggleButton value="cartesian">{t('upload.cartesianCoordinates')}</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            <Box sx={{ overflowX: 'auto' }} tabIndex={0} role="region" aria-label={t('upload.atomicPositionsTitle', { count: value.atoms.length })}>
              <Table size="small" stickyHeader aria-label={t('upload.atomicPositionsTitle', { count: value.atoms.length })} sx={tableSx}>
                <TableHead><TableRow><TableCell>{t('upload.atomLabel')}</TableCell>{(coordinates === 'fractional' ? ['u', 'v', 'w'] : ['x (Å)', 'y (Å)', 'z (Å)']).map(axis => <TableCell key={axis} align="right">{axis}</TableCell>)}</TableRow></TableHead>
                <TableBody>{value.atoms.map((atom, index) => <TableRow key={index}><TableCell component="th" scope="row">{atom.element}{index + 1}</TableCell>{atom[coordinates].map((number, i) => <TableCell key={i} align="right">{crystalNumber(number)}</TableCell>)}</TableRow>)}</TableBody>
              </Table>
            </Box>
          </Box>
        </>}
      </Box>
    </Box>
  </Box>
}
