import { Box, Typography } from '@mui/material'
import { useSearchParams } from 'react-router-dom'
import AccountReviews from '../components/AccountReviews'
import { useLanguage } from '../context/LanguageContext'
import AdminPage from './AdminPage'

/** 路由壳选择独立检查页，列表本身不递归承载自己的宿主。 */
export default function AdminWorkspacePage({ mode = 'admin' }: { mode?: 'admin' | 'superadmin' }) {
  const [params] = useSearchParams()
  const { t } = useLanguage()
  if (params.get('section') === 'papers' && params.has('review_tab')) {
    return <Box sx={{ py: 3 }}>
      <Typography variant="h4" sx={{ mb: 2 }}>{t('account.checkedPapers')}</Typography>
      <AccountReviews role={mode} fullPage />
    </Box>
  }
  return <AdminPage mode={mode} />
}
