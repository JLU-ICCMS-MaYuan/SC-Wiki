import {Alert,Button} from '@mui/material'
import {Link} from 'react-router-dom'
import {useLanguage} from '../context/LanguageContext'
export default function SystemCommunityPage(){const {t}=useLanguage();return <Alert severity="info" action={<Button component={Link} to="/search">{t('nav.search')}</Button>}>{t('search.systemRetired')}</Alert>}
