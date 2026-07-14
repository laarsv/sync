import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import Wordmark from '../components/Wordmark'

const ERRORS = {
  oauth_failed: 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.',
  email_unverified: 'Deine Google-Adresse ist nicht verifiziert.',
  wrong_domain: 'Diese Google-Adresse ist für diese Instanz nicht zugelassen.',
}

export default function Login() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [allowedDomain, setAllowedDomain] = useState('')
  const error = params.get('error')

  useEffect(() => {
    api
      .get('/config')
      .then((c) => setAllowedDomain(c?.allowed_email_domain || ''))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!loading && user) navigate('/', { replace: true })
  }, [loading, user, navigate])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ink">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="relative min-h-screen bg-ink overflow-hidden flex items-center justify-center">
      <div
        className="pointer-events-none absolute -top-32 -left-32 h-[520px] w-[820px] rounded-[50%] bg-royal-soft/20 blur-2xl"
        style={{ transform: 'rotate(-40deg)' }}
      />
      <div
        className="pointer-events-none absolute -bottom-40 -right-40 h-[420px] w-[680px] rounded-[50%] bg-royal/25 blur-3xl"
        style={{ transform: 'rotate(-40deg)' }}
      />

      <div className="relative z-10 w-full max-w-md px-4 sm:px-8 py-12 text-center">
        <Wordmark onInk className="text-5xl" />
        <p className="mt-4 text-sm text-paper/60 leading-relaxed">
          Google-Kalender-Sync.{' '}
          {allowedDomain
            ? `Anmeldung mit deiner @${allowedDomain}-Adresse.`
            : 'Anmeldung mit deinem Google-Konto.'}
        </p>

        {error && (
          <div className="mt-6 rounded-lg bg-red-50 border-l-4 border-red-500 text-red-900 p-3 text-sm text-left">
            {ERRORS[error] || 'Anmeldung nicht möglich.'}
          </div>
        )}

        <a
          href="/api/auth/google/login"
          className="mt-8 inline-flex w-full items-center justify-center rounded-lg bg-royal px-6 py-3
            text-base font-bold text-paper shadow-lg transition hover:bg-royal/90"
        >
          Mit Google anmelden
        </a>

        <div className="mt-10 text-sm font-black tracking-wordmark text-paper/50 select-none">
          vrwb<span className="text-royal wordmark-cursor-blink">_</span>
        </div>
      </div>
    </div>
  )
}
