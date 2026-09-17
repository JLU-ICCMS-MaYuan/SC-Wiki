import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '@mui/material'
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import { useLanguage } from '../../context/LanguageContext'
import SidebarButton from '../SidebarButton'

export default function CommunityNotificationLink({ collapsed }: { collapsed: boolean }) {
  const { user, token } = useAuth(); const { t } = useLanguage(); const navigate = useNavigate(); const [count, setCount] = useState(0)
  useEffect(() => {
    setCount(0); if (!user) return
    let stopped = false, pending = false
    const controller = new AbortController()
    const load = async () => { if (document.hidden || pending) return; pending = true; try { const result = await api.get<{ count: number }>('/api/community/notifications/unread', { signal: controller.signal }); if (!stopped) setCount(result.count) } catch { /* 消息列表提供可重试错误，角标不打断导航。 */ } finally { pending = false } }
    void load(); const timer = window.setInterval(() => void load(), 30000)
    window.addEventListener('community-notifications-changed', load); document.addEventListener('visibilitychange', load)
    return () => { stopped = true; controller.abort(); window.clearInterval(timer); window.removeEventListener('community-notifications-changed', load); document.removeEventListener('visibilitychange', load) }
  }, [user?.id, token])
  return <SidebarButton collapsed={collapsed} icon={<Badge badgeContent={count} color="error" max={99}><NotificationsOutlined /></Badge>} label={t('community.notifications')} onClick={() => navigate('/account/notifications')} />
}
