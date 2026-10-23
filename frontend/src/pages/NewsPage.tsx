import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Typography, Button } from '@mui/material'
import NewsFeed, { ManualNews } from '../components/NewsFeed'
import { useLanguage } from '../context/LanguageContext'
import { NobelGallery, NobelSurface } from '../features/nobel/NobelExperience'


const NewsPage: React.FC = () => {
  const navigate = useNavigate()
  const { t, lang } = useLanguage()

  return (
    <Box>
      {/* Hero */}
      <Box sx={{ textAlign: 'center', pt: { xs: 4, md: 6 }, pb: { xs: 3, md: 4 } }}>
        <Typography variant="overline" sx={{ display: 'block', maxWidth: 900, mx: 'auto', fontSize: 13, lineHeight: 1.6 }}>
          {t('news.heroAffiliation')}
        </Typography>
        <Typography variant="h1" sx={{ mt: 1 }}>
          {t('news.heroTitle')}
        </Typography>
        <Typography variant="body1" sx={{ mt: 2, maxWidth: 560, mx: 'auto', color: 'text.secondary', fontSize: 16, lineHeight: 1.8 }}>
          {t('news.heroSubtitle')}
        </Typography>
        <Box sx={{ mt: 3 }}>
          <Button variant="contained" size="large" onClick={() => navigate('/search')} sx={{ borderRadius: 2, px: 4, py: 1.25 }}>
            {t('news.startExploring')}
          </Button>
        </Box>
      </Box>

      {/* News Section */}
      <NewsFeed />
      <ManualNews />

      {/* 与独立Demo共用展陈、数据和图片，链接使用正式人物路由。 */}
      <NobelSurface><NobelGallery embedded lang={lang} /></NobelSurface>

    </Box>
  )
}

export default NewsPage
