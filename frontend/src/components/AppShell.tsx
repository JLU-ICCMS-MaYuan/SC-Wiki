import React, { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Avatar, Box, ButtonBase, Collapse, IconButton, ListItemIcon, Menu, MenuItem, Tooltip, Typography, useMediaQuery, useTheme } from '@mui/material'
import {
  AccountTreeOutlined, AdminPanelSettingsOutlined, AutoAwesomeOutlined, ChatBubbleOutline,
  ChevronLeft, ChevronRight, CloudUploadOutlined, ExploreOutlined, GroupsOutlined,
  LocalFireDepartmentOutlined, Logout as LogoutIcon, PersonOutline, VerifiedUserOutlined,
} from '@mui/icons-material'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import AuthDialog from './AuthDialog'
import LanguageSwitcher from './LanguageSwitcher'
import LlmProviderSwitcher from './LlmProviderSwitcher'
import SidebarButton from './SidebarButton'
import CommunityNotificationLink from './community/CommunityNotificationLink'

// path 是业务路由契约，文案与图标仅负责呈现。
const NAV_ITEMS = [
  { key: 'nav.news', path: '/news', icon: LocalFireDepartmentOutlined },
  { key: 'nav.search', path: '/search', icon: ExploreOutlined },
  { key: 'nav.knowledge', path: '/knowledge', icon: AccountTreeOutlined },
  { key: 'nav.share', path: '/share', icon: GroupsOutlined },
  { key: 'nav.upload', path: '/upload', icon: CloudUploadOutlined },
  { key: 'nav.rag', path: '/rag', icon: ChatBubbleOutline },
  { key: 'nav.tcPredict', path: '/tc-predict', icon: AutoAwesomeOutlined },
]

const ROLE_ICONS = { user: PersonOutline, admin: AdminPanelSettingsOutlined, superadmin: VerifiedUserOutlined }

const AppShell: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()
  const { t } = useLanguage()
  const theme = useTheme()
  const smallScreen = useMediaQuery(theme.breakpoints.down('md'))
  const [collapseChoice, setCollapseChoice] = useState<boolean | null>(null)
  const collapsed = collapseChoice ?? smallScreen
  const [authOpen, setAuthOpen] = useState(false)
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const [communityOpen, setCommunityOpen] = useState(location.pathname.startsWith('/share/'))
  const [communityAnchor, setCommunityAnchor] = useState<HTMLElement | null>(null)
  const communityItems = [
    { key: 'community.rankings', path: '/share/rankings' },
    { key: 'community.charts', path: '/share/charts' },
    { key: 'community.title', path: '/share/discussions' },
  ]
  const isActive = (path: string) => location.pathname === path || location.pathname.startsWith(`${path}/`)
  const accountActive = ['/account', '/admin', '/superadmin'].some(isActive)
  const RoleIcon = user ? ROLE_ICONS[user.role] : PersonOutline
  const collapseLabel = t(collapsed ? 'nav.expandSidebar' : 'nav.collapseSidebar')

  const handleLogout = () => {
    setAnchorEl(null)
    logout()
    navigate('/news')
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: `${collapsed ? 64 : 216}px minmax(0, 1fr)` }}>
      <Box component="nav" aria-label={t('nav.mainNav')} sx={{
        bgcolor: 'background.paper', borderRight: '1px solid', borderColor: 'divider',
        display: 'flex', flexDirection: 'column', p: collapsed ? '16px 8px' : '20px 12px',
        position: 'sticky', top: 0, alignSelf: 'start', height: '100dvh',
        boxSizing: 'border-box', overflowY: 'auto', overflowX: 'hidden',
        zIndex: theme => theme.zIndex.appBar - 1,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', flexDirection: collapsed ? 'column' : 'row', gap: 1, mb: 2, flexShrink: 0 }}>
          <Tooltip title={collapsed ? `SC-Wiki · ${t('nav.backHome')}` : ''} placement="right" arrow>
            <ButtonBase aria-label={`SC-Wiki · ${t('nav.backHome')}`} onClick={() => navigate('/')} sx={{
              display: 'flex', gap: 1.25, flex: collapsed ? undefined : 1, minWidth: 0, justifyContent: 'flex-start', borderRadius: 2,
              '&.Mui-focusVisible': { outline: '2px solid', outlineColor: 'primary.main' },
            }}>
              <Box component="span" sx={{ width: 40, height: 40, flexShrink: 0, borderRadius: '12px', bgcolor: 'primary.main', color: 'primary.contrastText', display: 'grid', placeItems: 'center', fontWeight: 800, boxShadow: '0 3px 8px rgba(79,70,229,0.2)' }}>SC</Box>
              {!collapsed && <Typography component="span" fontWeight={800} noWrap>SC-Wiki</Typography>}
            </ButtonBase>
          </Tooltip>
          <Tooltip title={collapseLabel} placement="right" arrow>
            <IconButton aria-label={collapseLabel} aria-expanded={!collapsed} onClick={() => { setAnchorEl(null); setCollapseChoice(!collapsed) }} size="small" sx={{ borderRadius: 1.5 }}>
              {collapsed ? <ChevronRight fontSize="small" /> : <ChevronLeft fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, flexShrink: 0 }}>
          {NAV_ITEMS.map(item => item.path === '/share' ? <React.Fragment key={item.path}>
            <SidebarButton icon={<GroupsOutlined />} label={t(item.key)} collapsed={collapsed} selected={isActive('/share')} aria-expanded={collapsed ? Boolean(communityAnchor) : communityOpen}
              onClick={event => collapsed ? setCommunityAnchor(event.currentTarget) : setCommunityOpen(value => !value)} />
            {!collapsed && <Collapse in={communityOpen}><Box sx={{ pl: 2 }}>{communityItems.map(child => <SidebarButton key={child.path} icon={<ChevronRight />} label={t(child.key)} selected={isActive(child.path)} onClick={() => navigate(child.path)} />)}</Box></Collapse>}
          </React.Fragment> : <SidebarButton
            key={item.path} icon={<item.icon />} label={t(item.key)} collapsed={collapsed}
            selected={isActive(item.path)} onClick={() => navigate(item.path)}
          />)}
        </Box>

        <Box sx={{ mt: 'auto', pt: 4, flexShrink: 0 }}>
          <Box sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 1 }}>
            <LlmProviderSwitcher collapsed={collapsed} />
            <LanguageSwitcher collapsed={collapsed} />
            {user ? (
              <>
              <CommunityNotificationLink collapsed={collapsed} />
              {['admin', 'superadmin'].includes(user.role) && <SidebarButton icon={<AdminPanelSettingsOutlined />} label={t('community.moderation')} collapsed={collapsed} selected={isActive('/admin/community')} onClick={() => navigate('/admin/community')} />}
              <Box sx={{ display: 'flex', alignItems: 'center', flexDirection: collapsed ? 'column' : 'row', gap: 0.5, mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                <SidebarButton icon={<RoleIcon />} label={t(`enums.role.${user.role}`)} detail={user.username} collapsed={collapsed} selected={accountActive} onClick={() => navigate('/account')} />
                <Tooltip title={t('nav.accountMenu')} placement="right" arrow>
                  <IconButton aria-label={t('nav.accountMenu')} aria-haspopup="menu" aria-expanded={Boolean(anchorEl)} onClick={event => setAnchorEl(event.currentTarget)} sx={{ p: 0.5 }}>
                    <Avatar src={user.avatar_url || undefined} sx={{ width: 28, height: 28, bgcolor: 'primary.main', fontSize: 12, fontWeight: 700 }}>
                      {user.username.charAt(0).toUpperCase()}
                    </Avatar>
                  </IconButton>
                </Tooltip>
              </Box>
              </>
            ) : <SidebarButton icon={<PersonOutline />} label={t('nav.login')} collapsed={collapsed} onClick={() => setAuthOpen(true)} />}
          </Box>
        </Box>
      </Box>

      <Box component="main" sx={{ p: { xs: 2, md: 4 }, minWidth: 0, width: '100%', boxSizing: 'border-box' }}>
        <Outlet />
      </Box>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)} anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }} transformOrigin={{ horizontal: 'left', vertical: 'bottom' }} slotProps={{ paper: { sx: { minWidth: 160 } } }}>
        <MenuItem onClick={handleLogout} sx={{ color: 'error.main' }}>
          <ListItemIcon><LogoutIcon fontSize="small" color="error" /></ListItemIcon>
          {t('nav.logout')}
        </MenuItem>
      </Menu>
      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
      <Menu anchorEl={communityAnchor} open={Boolean(communityAnchor)} onClose={() => setCommunityAnchor(null)}>
        {communityItems.map(item => <MenuItem key={item.path} selected={isActive(item.path)} onClick={() => { setCommunityAnchor(null); navigate(item.path) }}>{t(item.key)}</MenuItem>)}
      </Menu>
    </Box>
  )
}

export default AppShell
