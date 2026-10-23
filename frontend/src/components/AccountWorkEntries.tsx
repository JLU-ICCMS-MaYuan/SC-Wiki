import React from 'react'
import { Link } from 'react-router-dom'
import { PeopleOutline, PersonAddAltOutlined, BarChartOutlined, NewspaperOutlined, Tune, HistoryOutlined, ArrowOutward } from '@mui/icons-material'
import { useLanguage } from '../context/LanguageContext'

const entries = [
  { section: 'users', title: 'admin.usersPermissions', hint: 'account.usersHint', icon: PeopleOutline },
  { section: 'applications', title: 'admin.applicationsTab', hint: 'account.applicationsHint', icon: PersonAddAltOutlined },
  { section: 'charts', title: 'admin.cardChartGroups', hint: 'account.chartsHint', icon: BarChartOutlined },
  { section: 'news', title: 'admin.newsTitle', hint: 'account.newsHint', icon: NewspaperOutlined },
  { section: 'models', title: 'account.modelsTitle', hint: 'account.modelsHint', icon: Tune },
  { section: 'audit', title: 'admin.auditTab', hint: 'account.auditHint', icon: HistoryOutlined },
]
export default function AccountWorkEntries() {
  const { t } = useLanguage()
  return <div className="account-work-grid">{entries.map(({ section, title, hint, icon: Icon }) => <Link key={section} to={`/superadmin?section=${section}`} target="_blank" rel="noopener noreferrer" className="account-work-entry"><span><Icon /><ArrowOutward /></span><h3>{t(title)}</h3><p>{t(hint)}</p></Link>)}</div>
}
