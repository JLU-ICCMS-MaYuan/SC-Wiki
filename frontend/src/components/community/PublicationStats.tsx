import React, { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Alert, Box, Button, Card, CardContent, CircularProgress, Typography } from '@mui/material'
import { Refresh } from '@mui/icons-material'
import { api } from '../../lib/api'
import { familyName } from '../../lib/classifications'
import { useLanguage } from '../../context/LanguageContext'

interface PublicationYear {
  year: number
  paper_count: number
}

interface PublicationFamily {
  family_id: number
  name_zh: string
  name_en: string
  paper_count: number
  unknown_year_count: number
  years: PublicationYear[]
}

interface PublicationSnapshot {
  families: PublicationFamily[]
  generated_at: string
}

interface CountColumn {
  id: number
  label: string
  count: number
}

// 两张图复用相同的线性刻度；整列按钮让零篇家族也可点击、聚焦和键盘选择。
function PublicationBars({ columns, axis, selected, onSelect, controls }: {
  columns: CountColumn[]
  axis: string
  selected?: number | null
  onSelect?: (id: number) => void
  controls?: string
}) {
  const { t } = useLanguage()
  const maximum = columns.reduce((max, item) => Math.max(max, item.count), 1)
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">{t('share.publicationCountAxis')}</Typography>
      <Box sx={{ display: 'flex', minWidth: 0 }}>
        <Box aria-hidden="true" sx={{ width: 48, flexShrink: 0, height: 224, position: 'relative' }}>
          <Typography variant="caption" sx={{ position: 'absolute', right: 8, top: 16 }}>{maximum}</Typography>
          <Typography variant="caption" sx={{ position: 'absolute', right: 8, bottom: -8 }}>0</Typography>
        </Box>
        <Box role="group" aria-label={axis} sx={{ overflowX: 'auto', minWidth: 0, flex: 1, pb: 1 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: `repeat(${columns.length}, minmax(88px, 1fr))`, minWidth: columns.length * 88 }}>
            {columns.map(column => {
              const active = selected === column.id
              return (
                <Box key={column.id} component={onSelect ? 'button' : 'div'}
                  type={onSelect ? 'button' : undefined}
                  aria-label={t('share.publicationColumnLabel', { name: column.label, count: column.count })}
                  aria-pressed={onSelect ? active : undefined}
                  aria-expanded={onSelect ? active : undefined}
                  aria-controls={onSelect && active ? controls : undefined}
                  onClick={onSelect ? () => onSelect(column.id) : undefined}
                  sx={{
                    p: 0, m: 0, border: 0, borderRadius: 1, bgcolor: active ? 'action.selected' : 'transparent',
                    color: 'text.primary', font: 'inherit', minWidth: 0, alignSelf: 'stretch', textAlign: 'center',
                    display: 'flex', flexDirection: 'column', cursor: onSelect ? 'pointer' : 'default',
                    '&:hover': onSelect ? { bgcolor: 'action.hover' } : {},
                    '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 },
                  }}>
                  <Box sx={{ height: 224, pt: '24px', width: '100%', borderBottom: 1, borderColor: 'divider', boxSizing: 'border-box' }}>
                    <Box sx={{ height: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
                      <Box data-testid={`publication-bar-${axis}-${column.id}`} sx={{
                        height: `${column.count / maximum * 100}%`, width: '60%', maxWidth: 64,
                        bgcolor: active ? 'primary.dark' : 'primary.main', borderRadius: '4px 4px 0 0', position: 'relative',
                      }}>
                        <Typography component="span" variant="caption" sx={{ position: 'absolute', top: -22, left: 0, width: '100%', fontWeight: 700 }}>
                          {column.count}
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                  <Typography component="span" variant="caption" sx={{ display: 'block', p: 1, overflowWrap: 'anywhere', fontWeight: active ? 800 : 500 }}>
                    {column.label}
                  </Typography>
                </Box>
              )
            })}
          </Box>
        </Box>
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1 }}>{axis}</Typography>
    </Box>
  )
}

export default function PublicationStats({ refreshToken = 0 }: { refreshToken?: number }) {
  const { t, lang } = useLanguage()
  const annualId = useId()
  const [snapshot, setSnapshot] = useState<PublicationSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const requestSequence = useRef(0)
  const previousRefresh = useRef(refreshToken)

  const load = useCallback(async (force = false) => {
    const sequence = ++requestSequence.current
    setLoading(true)
    try {
      const next = await api.get<PublicationSnapshot>(`/api/community/publication-stats${force ? '?refresh=true' : ''}`)
      if (sequence !== requestSequence.current) return
      setSnapshot(next)
      setFailed(false)
      setSelectedId(current => next.families.some(f => f.family_id === current) ? current : null)
    } catch {
      if (sequence === requestSequence.current) setFailed(true)
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => { void load() }, 60 * 60 * 1000)
    return () => { window.clearInterval(timer); requestSequence.current++ }
  }, [load])

  useEffect(() => {
    if (previousRefresh.current === refreshToken) return
    previousRefresh.current = refreshToken
    void load(true)
  }, [refreshToken, load])

  const name = (family: PublicationFamily) => family.family_id === 0
    ? t('share.publicationUnclassified') : familyName(family, lang)
  const selected = snapshot?.families.find(f => f.family_id === selectedId)
  const annualTitle = selected ? t('share.publicationAnnualTitle', { name: name(selected) }) : ''

  return (
    <Card sx={{ mb: 3, minWidth: 0 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap', mb: 2 }}>
          <Box>
            <Typography variant="h5">{t('share.publicationTitle')}</Typography>
            {snapshot && <Typography variant="caption" color="text.secondary">
              {t('share.lastUpdated', { time: new Date(snapshot.generated_at).toLocaleString(lang === 'zh' ? 'zh-CN' : 'en-US') })}
            </Typography>}
          </Box>
          <Button variant="outlined" disabled={loading} onClick={() => void load(true)}
            startIcon={loading ? <CircularProgress size={16} /> : <Refresh />}>
            {t('share.publicationRefresh')}
          </Button>
        </Box>
        <Typography color="text.secondary" variant="body2" sx={{ mb: 2 }}>{t('share.publicationScope')}</Typography>
        {failed && <Alert severity="warning" sx={{ mb: 2 }}
          action={<Button color="inherit" disabled={loading} onClick={() => void load(true)}>{t('share.publicationRetry')}</Button>}>
          {t('share.publicationFailed')}
        </Alert>}
        {loading && !snapshot && <Box role="status" sx={{ py: 3 }}>{t('share.publicationLoading')}</Box>}
        {snapshot && <>
          {!snapshot.families.some(f => f.paper_count > 0) && <Typography color="text.secondary" sx={{ mb: 2 }}>{t('share.publicationEmpty')}</Typography>}
          {snapshot.families.length > 0 && <PublicationBars
            columns={snapshot.families.map(f => ({ id: f.family_id, label: name(f), count: f.paper_count }))}
            axis={t('share.materialFamily')} selected={selectedId} controls={annualId}
            onSelect={id => setSelectedId(current => current === id ? null : id)}
          />}
          <Typography variant="caption" color="text.secondary">{t('share.publicationSelectHint')}</Typography>
          {selected && <Box id={annualId} role="region" aria-label={annualTitle} sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: 'divider', minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="h6">{annualTitle}</Typography>
              <Button onClick={() => setSelectedId(null)}>{t('share.publicationCollapse')}</Button>
            </Box>
            <Typography color="text.secondary" variant="body2" sx={{ mb: 2 }}>
              {t('share.publicationUnknownYear', { count: selected.unknown_year_count })}
            </Typography>
            {selected.years.length > 0 ? <PublicationBars
              columns={selected.years.map(year => ({ id: year.year, label: String(year.year), count: year.paper_count }))}
              axis={t('share.publicationYearAxis')}
            /> : <Typography color="text.secondary">
              {t(selected.paper_count === 0 ? 'share.publicationFamilyEmpty' : 'share.publicationNoYears')}
            </Typography>}
          </Box>}
        </>}
      </CardContent>
    </Card>
  )
}
