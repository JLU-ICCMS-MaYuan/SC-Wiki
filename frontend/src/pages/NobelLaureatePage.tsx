import { useParams } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import { NobelDetail, NobelSurface } from '../features/nobel/NobelExperience'
import { getLaureates, copy } from '../features/nobel/copy'

export default function NobelLaureatePage() {
  const { personId } = useParams()
  const { lang } = useLanguage()
  const person = getLaureates(lang).find(entry => entry.id === personId)
  return <NobelSurface>{person
    ? <NobelDetail person={person} lang={lang} />
    : <section className="nobel-detail"><h1>{copy[lang].notFound}</h1><a href="/news#nobel-milestones">{copy[lang].back}</a></section>}
  </NobelSurface>
}
