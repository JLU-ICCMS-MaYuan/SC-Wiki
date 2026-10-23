import { NobelDetail, NobelGallery, NobelSurface } from '../../features/nobel/NobelExperience'
import { getLaureates } from '../../features/nobel/copy'

export default function NobelDemo() {
  const params = new URLSearchParams(window.location.search)
  const lang = params.get('lang') === 'en' ? 'en' : 'zh'
  const person = getLaureates(lang).find(entry => entry.id === params.get('person'))
  const home = `/nobel-demo.html?lang=${lang}`
  return <NobelSurface>{person
    ? <NobelDetail person={person} lang={lang} backHref={home} />
    : <NobelGallery lang={lang} detailHref={id => `${home}&person=${id}`} />}</NobelSurface>
}
