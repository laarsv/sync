import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'

// Google leitet nach dem Calendar-Consent hierher (SPA-Route). Wir posten den
// Code ans Backend, das die Tokens verschluesselt ablegt.
export default function CalendarCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState(null)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    const code = params.get('code')
    const state = params.get('state')
    const oauthError = params.get('error')

    if (oauthError) {
      setError('Consent abgebrochen oder verweigert.')
      return
    }
    if (!code || !state) {
      setError('Fehlende OAuth-Parameter.')
      return
    }

    api
      .post('/calendar/callback', {
        code,
        state,
        redirect_uri: `${window.location.origin}/calendar/callback`,
      })
      .then(() => navigate('/connect?connected=1', { replace: true }))
      .catch((e) => setError(e.message))
  }, [params, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      {error ? (
        <div className="max-w-md w-full card p-6 text-center">
          <h1 className="text-lg font-black">Verbindung fehlgeschlagen</h1>
          <p className="mt-2 text-sm text-ink/70">{error}</p>
          <button
            className="btn-primary mt-6"
            onClick={() => navigate('/connect', { replace: true })}
          >
            Zurück
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <Spinner size="lg" />
          <p className="text-sm text-ink/60">Kalender wird verbunden…</p>
        </div>
      )}
    </div>
  )
}
