import React, { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Box, CircularProgress } from '@mui/material'

const SearchPage = lazy(() => import('./pages/SearchPage'))
const RagPage = lazy(() => import('./pages/RagPage'))
const TcPredictPage = lazy(() => import('./pages/TcPredictPage'))
const SharePage = lazy(() => import('./pages/share'))
const KnowledgeGraphPage = lazy(() => import('./pages/KnowledgeGraphPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))
const AdminPaperEditPage = lazy(() => import('./pages/AdminPaperEditPage'))
const UploadPage = lazy(() => import('./pages/UploadPage'))
const PaperDetailPage = lazy(() => import('./pages/PaperDetailPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const PublicUserPage = lazy(() => import('./pages/PublicUserPage'))
const SuperAdminPage = lazy(() => import('./pages/SuperAdminPage'))
const RoleRoute = lazy(() => import('./components/RoleRoute'))
const DiscussionPage = lazy(() => import('./pages/DiscussionPage'))
const SystemCommunityPage = lazy(() => import('./pages/SystemCommunityPage'))
const CommunityNotificationsPage = lazy(() => import('./pages/CommunityNotificationsPage'))
const CommunityModerationPage = lazy(() => import('./pages/CommunityModerationPage'))

const Spin: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense fallback={
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
      <CircularProgress />
    </Box>
  }>
    {children}
  </Suspense>
)

const LazyRoutes: React.FC = () => (
  <Routes>
    <Route path="/search" element={<Spin><SearchPage /></Spin>} />
    <Route path="/share" element={<Navigate to="/share/charts" replace />} />
    <Route path="/share/charts" element={<Spin><SharePage section="charts" /></Spin>} />
    <Route path="/share/rankings" element={<Spin><SharePage section="rankings" /></Spin>} />
    <Route path="/share/discussions" element={<Spin><DiscussionPage /></Spin>} />
    <Route path="/share/discussions/:id" element={<Spin><DiscussionPage /></Spin>} />
    <Route path="/systems/:systemKey" element={<Spin><SystemCommunityPage /></Spin>} />
    <Route path="/account/notifications" element={<Spin><RoleRoute allow={['user', 'admin', 'superadmin']}><CommunityNotificationsPage /></RoleRoute></Spin>} />
    <Route path="/admin/community" element={<Spin><RoleRoute allow={['admin', 'superadmin']}><CommunityModerationPage /></RoleRoute></Spin>} />
    <Route path="/upload" element={<Spin><UploadPage /></Spin>} />
    {/* 论文可见性按论文状态与归属逐篇由后端裁决，因此不包裹 RoleRoute */}
    <Route path="/papers/:id" element={<Spin><PaperDetailPage /></Spin>} />
    <Route path="/rag" element={<Spin><RagPage /></Spin>} />
    <Route path="/tc-predict" element={<Spin><TcPredictPage /></Spin>} />
    <Route path="/knowledge" element={<Spin><KnowledgeGraphPage /></Spin>} />
    <Route path="/account" element={<Spin><RoleRoute allow={['user', 'admin', 'superadmin']}><AccountPage /></RoleRoute></Spin>} />
    <Route path="/users/:username" element={<Spin><PublicUserPage /></Spin>} />
    <Route path="/admin" element={<Spin><RoleRoute allow={['admin']} redirectSuperadminFromAdmin><AdminPage /></RoleRoute></Spin>} />
    {/* Issue #78：超管复用管理员论文列表，需能进入同一篇论文的独立编辑页。 */}
    <Route path="/admin/papers/:id/edit" element={<Spin><RoleRoute allow={['admin', 'superadmin']}><AdminPaperEditPage /></RoleRoute></Spin>} />
    <Route path="/superadmin" element={<Spin><RoleRoute allow={['superadmin']}><SuperAdminPage /></RoleRoute></Spin>} />
    {/* 兜底：未匹配地址显示明确提示，避免白屏 */}
    <Route path="*" element={<Spin><NotFoundPage /></Spin>} />
  </Routes>
)

export default LazyRoutes
