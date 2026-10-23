import React, { useState } from 'react'
import { Box, Button, Tab, Tabs } from '@mui/material'
import { OpenInNew } from '@mui/icons-material'
import { Link } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import MyPapersList from './MyPapersList'
import AdminPage from '../pages/AdminPage'

export default function AccountReviews({ role }: { role: 'admin' | 'superadmin' }) {
  const { t } = useLanguage()
  const [tab, setTab] = useState(0)
  return <><Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', mb: 2, gap: 1 }}><Tabs value={tab} onChange={(_, value) => setTab(value)}><Tab label={t('account.checkedHistory')} /><Tab label={t('account.pendingChecks')} /></Tabs><Button component={Link} to={`/${role}?section=papers`} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew />} sx={{ ml: 'auto' }}>{t('account.openReview')}</Button></Box>{tab === 0 ? <MyPapersList kind="reviews" /> : <AdminPage mode={role} embedded />}</>
}
