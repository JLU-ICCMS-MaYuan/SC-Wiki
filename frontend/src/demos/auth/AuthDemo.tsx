import React, { useState } from 'react'
import AuthExperience from '../../features/auth/AuthExperience'
import { useLanguage } from '../../context/LanguageContext'
import { authDemoCopy } from './copy'
import { createDemoAuth, DEMO_PASSWORD } from './mockAuth'

export default function AuthDemo() {
  const [auth] = useState(createDemoAuth)
  const { lang } = useLanguage()
  return <AuthExperience auth={auth} demo copyOverride={authDemoCopy[lang]}
    demoAccounts={{ verified: 'researcher@example.com', unverified: 'unverified@example.com', password: DEMO_PASSWORD }} />
}
