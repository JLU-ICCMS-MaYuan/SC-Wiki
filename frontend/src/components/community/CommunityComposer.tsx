import React, { useState } from 'react'
import { Alert, Box, Button, Stack, TextField, Typography } from '@mui/material'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import { communityErrorKey } from '../../lib/community'
import AuthDialog from '../AuthDialog'
import CommunityMarkdown from './CommunityMarkdown'

interface Props { onSubmit: (body: string, title: string) => Promise<void>; question?: boolean; markdown?: boolean; initialBody?: string; initialTitle?: string; submitLabel?: string; onCancel?: () => void; maxLength?: number; label?: string }
export default function CommunityComposer({ onSubmit, question = false, markdown = false, initialBody = '', initialTitle = '', submitLabel, onCancel, maxLength = 2000, label }: Props) {
  const { user } = useAuth(); const { t } = useLanguage()
  const [body, setBody] = useState(initialBody), [title, setTitle] = useState(initialTitle)
  const [busy, setBusy] = useState(false), [preview, setPreview] = useState(false), [error, setError] = useState(''), [login, setLogin] = useState(false)
  if (!user) return <><Button onClick={() => setLogin(true)}>{t('community.login')}</Button><AuthDialog open={login} onClose={() => setLogin(false)} /></>
  if (!user.is_email_verified) return <Alert severity="info">{t('community.verify')}</Alert>
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy) return
    setBusy(true); setError('')
    try { await onSubmit(body.trim(), title.trim()); setBody(''); setTitle(''); setPreview(false) } catch (reason) { setError(communityErrorKey(reason)) } finally { setBusy(false) }
  }
  return <Box component="form" onSubmit={event => void submit(event)} sx={{ my: 1.5 }}>
    <Stack spacing={1.5}>
      {question && <TextField label={t('community.questionTitle')} value={title} onChange={e => setTitle(e.target.value)} disabled={busy} inputProps={{ maxLength: 200 }} required fullWidth />}
      {preview ? <CommunityMarkdown content={body} /> : <TextField label={label || t(question ? 'community.questionBody' : 'community.body')} value={body} onChange={e => setBody(e.target.value)} disabled={busy} multiline minRows={markdown ? 5 : 2} fullWidth required={!question} inputProps={{ maxLength: maxLength * 2 }} />}
      <Typography variant="caption" color="text.secondary">{Array.from(body).length}/{maxLength}{markdown ? ` · ${t('community.markdownHelp')}` : ''}</Typography>
      {error && <Alert severity="error">{t(error)}</Alert>}
      <Stack direction="row" spacing={1}>
        <Button type="submit" variant="contained" disabled={busy || Array.from(body).length > maxLength || (!question && !body.trim()) || (question && (Array.from(title.trim()).length < 3 || Array.from(title).length > 200))}>{t(busy ? 'community.publishing' : (submitLabel || 'community.publish'))}</Button>
        {markdown && <Button disabled={busy} onClick={() => setPreview(v => !v)}>{t(preview ? 'community.write' : 'community.preview')}</Button>}
        {onCancel && <Button disabled={busy} onClick={onCancel}>{t('community.cancel')}</Button>}
      </Stack>
    </Stack>
  </Box>
}
