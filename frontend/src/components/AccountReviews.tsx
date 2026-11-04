import { useState } from 'react'
import { Box, Button, Tab, Tabs } from '@mui/material'
import { OpenInNew } from '@mui/icons-material'
import { Link, useSearchParams } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import MyPapersList from './MyPapersList'
import AdminPage from '../pages/AdminPage'

export default function AccountReviews({ role, fullPage = false }: { role: 'admin' | 'superadmin'; fullPage?: boolean }) {
  const { t } = useLanguage()
  const [params] = useSearchParams()
  const [tab, setTab] = useState(fullPage && params.get('review_tab') === 'pending' ? 1 : 0)
  const pageSize = fullPage ? 20 : 3
  return <>
    <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', mb: 2, gap: 1 }}>
      <Tabs value={tab} onChange={(_, value) => setTab(value)}>
        <Tab label={t('account.checkedHistory')} /><Tab label={t('account.pendingChecks')} />
      </Tabs>
      {!fullPage && <Button component={Link}
        to={'/' + role + '?section=papers&review_tab=' + (tab ? 'pending' : 'history')}
        target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew />} sx={{ ml: 'auto' }}>
        {t('account.openReview')}
      </Button>}
    </Box>
    {tab === 0 ? <MyPapersList kind="reviews" pageSize={pageSize} scrollable={fullPage} />
      : <AdminPage mode={role} embedded pageSize={pageSize} scrollable={fullPage} />}
  </>
}
