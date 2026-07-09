import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Spinner from '../components/ui/Spinner'

const ERRORS = {
  oauth_failed: 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.',
  email_unverified: 'Deine Google-Adresse ist nicht verifiziert.',
  wrong_domain: 'Login nur mit @koenigswege.com-Adressen möglich.',
}

export default function Login() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const error = params.get('error')

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
        <div className="flex items-center justify-center gap-3 text-paper">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-royal">
            <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 10a8 8 0 0 1 13.7-4.5L20 8" />
              <path d="M20 14a8 8 0 0 1-13.7 4.5L4 16" />
              <path d="M20 4v4h-4M4 20v-4h4" />
            </svg>
          </span>
          <span className="text-4xl font-black tracking-wordmark">Sync</span>
        </div>
        <p className="mt-4 text-sm text-paper/60 leading-relaxed">
          Google-Kalender-Sync fürs Königswege-Team. Anmeldung mit deiner
          @koenigswege.com-Adresse.
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
      </div>
    </div>
  )
}
