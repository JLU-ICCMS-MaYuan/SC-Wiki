import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Alert, Avatar, Box, Button, Card, CardContent, Chip, CircularProgress,
  Stack, TextField, Typography,
} from '@mui/material'
import { AdminPanelSettings, DeleteOutline, OpenInNew, PhotoCamera, EditOutlined, DescriptionOutlined, FactCheckOutlined, InfoOutlined } from '@mui/icons-material'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import UsernameField from '../components/UsernameField'
import MyPapersList from '../components/MyPapersList'
import AccountSecurity from '../components/AccountSecurity'
import AccountWorkEntries from '../components/AccountWorkEntries'
import AccountReviews from '../components/AccountReviews'
import './account.css'

interface Profile {
  id: number
  email: string
  username: string
  username_change_allowed: boolean
  real_name: string
  affiliation: string | null
  orcid: string | null
  research_interests: string[] | null
  avatar_url: string | null
  role: 'user' | 'admin' | 'superadmin'
  is_email_verified: boolean
  account_status: string
}

interface AdminApplication {
  id: number
  status: 'pending' | 'approved' | 'rejected' | 'withdrawn'
  rejection_reason?: string | null
  submitted_at: string
}

const AccountPage: React.FC = () => {
  const { user, replaceUser, updateUsername } = useAuth()
  const { t } = useLanguage()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [applications, setApplications] = useState<AdminApplication[]>([])
  const [realName, setRealName] = useState('')
  const [affiliation, setAffiliation] = useState('')
  const [orcid, setOrcid] = useState('')
  const [interests, setInterests] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [message, setMessage] = useState<{ severity: 'success' | 'error' | 'info'; text: string } | null>(null)

  const pendingApplication = useMemo(() => applications.find(item => item.status === 'pending'), [applications])

  /**
   * 错误消息映射：AuthContext 抛出的 Error.message 是机器键（如 'usernameUpdateFailed'），
   * 此处映射为 `account.*` 字典文案（随语言切换）；api 层返回的后端原文原样显示。
   */
  const errorText = (error: unknown): string => {
    const message = (error as Error).message
    const key = `account.${message}`
    const mapped = t(key)
    return mapped === key ? message : mapped
  }

  const load = async () => {
    const data = await api.get<Profile>('/api/account/profile')
    setProfile(data)
    setRealName(data.real_name || '')
    setAffiliation(data.affiliation || '')
    setOrcid(data.orcid || '')
    setInterests((data.research_interests || []).join('，'))
    if (data.role === 'user') setApplications(await api.get<AdminApplication[]>('/api/account/admin-applications'))
  }

  useEffect(() => {
    void load().catch(error => setMessage({ severity: 'error', text: errorText(error) })).finally(() => setInitialLoading(false))
  }, [])

  const run = async (action: () => Promise<void>, success: string) => {
    setBusy(true)
    setMessage(null)
    try {
      await action()
      setMessage({ severity: 'success', text: success })
    } catch (error) {
      setMessage({ severity: 'error', text: errorText(error) })
    } finally {
      setBusy(false)
    }
  }

  if (initialLoading) return <Box sx={{ minHeight: '55vh', display: 'grid', placeItems: 'center' }}><CircularProgress /></Box>
  if (!profile || !user) return <Alert severity="error">{message?.text || t('account.profileLoadFailed')}</Alert>

  const profileInterests = profile.research_interests ?? []

  const saveProfile = () => {
    if (realName && !profile.real_name && !window.confirm(t('account.realNameConfirm'))) return
    void run(async () => {
    const researchInterests = interests.split(/[，,]/).map(value => value.trim()).filter(Boolean)
    const updated = await api.patch<Profile>('/api/account/profile', { real_name: realName, affiliation, orcid, research_interests: researchInterests })
    setProfile(updated)
    setEditing(false)
    }, t('account.profileSaved'))
  }

  const uploadAvatar = (file?: File) => {
    if (!file) return
    void run(async () => {
      const form = new FormData()
      form.append('avatar', file)
      const result = await api.post<{ avatar_url: string }>('/api/account/avatar', form)
      const next = { ...profile, avatar_url: result.avatar_url }
      setProfile(next)
      replaceUser({ ...user, avatar_url: result.avatar_url })
    }, t('account.avatarUpdated'))
  }

  return (
    <Box className="account-center">
      <Typography variant="overline" color="primary" fontWeight={700}>ACCOUNT</Typography>
      <Typography variant="h3" fontWeight={800} sx={{ fontSize: 28, mt: 0.5 }}>{t('account.title')}</Typography>
      <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>{t('account.subtitle')}</Typography>
      {message && <Alert severity={message.severity} onClose={() => setMessage(null)} sx={{ mb: 2 }}>{message.text}</Alert>}

      <section className="account-card account-profile">
        <div className="account-profile-top">
          <Avatar src={profile.avatar_url || undefined} className="account-avatar">{profile.username[0]?.toUpperCase()}</Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap"><Typography variant="h5" fontWeight={650}>{profile.real_name || profile.username}</Typography><Chip size="small" label={t(`enums.role.${profile.role}`)} color="primary" variant="outlined" /></Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>@{profile.username}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{profile.email}{profile.is_email_verified ? ' · ' + t('account.emailVerified') : ''}</Typography>
          </Box>
          <Stack direction="row" gap={1} flexWrap="wrap" className="account-profile-actions">
            <Button component={Link} to={`/users/${profile.username}`} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew />}>{t('account.viewPublicProfile')}</Button>
            {!editing && <Button variant="contained" startIcon={<EditOutlined />} disabled={busy} onClick={() => { setRealName(profile.real_name || ''); setAffiliation(profile.affiliation || ''); setOrcid(profile.orcid || ''); setInterests((profile.research_interests || []).join('，')); setEditing(true) }}>{t('account.editProfile')}</Button>}
          </Stack>
        </div>
        <div className="account-profile-fields">
          {editing ? <>
            <TextField autoFocus label={t('account.realName')} value={realName} onChange={e => setRealName(e.target.value)} disabled={busy} helperText={t('account.realNameHelper')} />
            <TextField label={t('account.affiliation')} value={affiliation} onChange={e => setAffiliation(e.target.value)} disabled={busy} />
            <TextField label="ORCID" value={orcid} onChange={e => setOrcid(e.target.value)} disabled={busy} placeholder="0000-0002-1825-0097" />
            <TextField className="account-research" label={t('account.researchInterests')} value={interests} onChange={e => setInterests(e.target.value)} disabled={busy} helperText={t('account.interestsHelper')} />
          </> : <>
            {[[t('account.realName'), profile.real_name], [t('account.affiliation'), profile.affiliation], ['ORCID', profile.orcid]].map(([label, value]) => <div key={label}><span className="account-field-label">{label}</span><Typography sx={{ overflowWrap: 'anywhere' }}>{value || t('account.notProvided')}</Typography></div>)}
            <div className="account-research"><span className="account-field-label">{t('account.researchInterests')}</span><Stack direction="row" gap={1} flexWrap="wrap">{profileInterests.length ? profileInterests.map(item => <Chip size="small" key={item} label={item} />) : <Typography color="text.secondary">{t('account.notProvided')}</Typography>}</Stack></div>
          </>}
        </div>
        {editing && <Stack direction="row" gap={1} sx={{ px: 3, pb: 2 }} flexWrap="wrap"><Button component="label" disabled={busy} startIcon={<PhotoCamera />}>{t('account.uploadAvatar')}<input hidden type="file" disabled={busy} accept="image/jpeg,image/png,image/webp" onChange={event => uploadAvatar(event.target.files?.[0])} /></Button>{profile.avatar_url && <Button color="error" disabled={busy} startIcon={<DeleteOutline />} onClick={() => void run(async () => { await api.del('/api/account/avatar'); setProfile({ ...profile, avatar_url: null }); replaceUser({ ...user, avatar_url: null }) }, t('account.avatarDeleted'))}>{t('common.delete')}</Button>}</Stack>}
        <div className="account-profile-footer"><Typography variant="caption" color="text.secondary"><InfoOutlined fontSize="inherit" /> {t('account.profilePrivacyHint')}</Typography>{editing && <Stack direction="row" gap={1}><Button disabled={busy} onClick={() => setEditing(false)}>{t('common.cancel')}</Button><Button variant="contained" disabled={busy} onClick={saveProfile}>{t('account.saveProfile')}</Button></Stack>}</div>
      </section>

      {profile.username_change_allowed && (
        <Card variant="outlined" sx={{ mb: 3, borderRadius: 3 }}><CardContent sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight={750}>{t('account.setUsernameTitle')}</Typography>
          <Alert severity="warning" sx={{ my: 2 }}>{t('account.usernameChangeWarning')}</Alert>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="start">
            <Box sx={{ flex: 1, width: '100%' }}><UsernameField value={newUsername} onChange={setNewUsername} /></Box>
            <Button variant="outlined" disabled={busy || !newUsername} onClick={() => void run(async () => { await updateUsername(newUsername); await load() }, t('account.usernameUpdated'))}>{t('account.confirmChange')}</Button>
          </Stack>
        </CardContent></Card>
      )}

      <section className="account-card"><div className="account-section-heading"><span className="account-section-icon"><DescriptionOutlined /></span><div><h2>{t('account.myPapers')}</h2><p>{t('account.myPapersHint')}</p></div></div><MyPapersList /></section>
      {profile.role !== 'user' && <section className="account-card"><div className="account-section-heading"><span className="account-section-icon"><FactCheckOutlined /></span><div><h2>{t('account.checkedPapers')}</h2><p>{t('account.checkedPapersHint')}</p></div></div><AccountReviews role={profile.role} /></section>}
      <AccountSecurity />

      <Card variant="outlined" sx={{ borderRadius: 3 }}><CardContent sx={{ p: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center"><AdminPanelSettings color="primary" /><Typography variant="h6" fontWeight={750}>{t('account.workSection')}</Typography></Stack>
        {profile.role === 'admin' && <Button component={Link} to="/admin?section=papers" target="_blank" rel="noopener noreferrer" variant="outlined" sx={{ mt: 2 }} endIcon={<OpenInNew />}>{t('account.openReview')}</Button>}
        {profile.role === 'superadmin' && <><Typography variant="body2" color="text.secondary" sx={{ mt: 1, mb: 2 }}>{t('account.workHint')}</Typography><AccountWorkEntries /></>}
        {profile.role === 'user' && (
          <Box sx={{ mt: 2 }}>
            <Typography color="text.secondary">{t('account.adminApplyHint')}</Typography>
            <Button variant="contained" sx={{ mt: 1.5 }} disabled={busy || Boolean(pendingApplication)} onClick={() => void run(async () => { await api.post('/api/account/admin-applications'); await load() }, t('account.adminApplied'))}>{t('account.applyAdmin')}</Button>
            {applications.length > 0 && <Stack spacing={1} sx={{ mt: 2 }}>{applications.map(item => <Box key={item.id} sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: 2 }}><Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Chip size="small" label={t(`account.applicationStatus.${item.status}`)} /><Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>{new Date(item.submitted_at).toLocaleString()}</Typography>{item.rejection_reason && <Typography color="error" variant="body2" sx={{ mt: 0.5 }}>{t('account.rejectionReason', { reason: item.rejection_reason || '' })}</Typography>}</Box>{item.status === 'pending' && <Button size="small" color="warning" onClick={() => void run(async () => { await api.post(`/api/account/admin-applications/${item.id}/withdraw`); await load() }, t('account.applicationWithdrawn'))}>{t('account.withdraw')}</Button>}</Stack></Box>)}</Stack>}
          </Box>
        )}
      </CardContent></Card>
    </Box>
  )
}

export default AccountPage
