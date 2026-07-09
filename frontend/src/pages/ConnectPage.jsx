import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import Pill from '../components/ui/Pill'
import { Calendar, LinkIcon } from '../components/ui/Icons'

const ROLE_LABEL = {
  owner: 'Eigentümer',
  writer: 'Schreiben',
  reader: 'Lesen',
  freeBusyReader: 'nur frei/gebucht',
}

export default function ConnectPage() {
  const [params] = useSearchParams()
  const [status, setStatus] = useState(null)
  const [calendars, setCalendars] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const justConnected = params.get('connected') === '1'

  const load = useCallback(async () => {
    setError(null)
    try {
      const st = await api.get('/calendar/status')
      setStatus(st)
      if (st.connected) {
        try {
          setCalendars(await api.get('/calendar/calendars'))
        } catch (e) {
          setCalendars([])
          if (e instanceof ApiError && e.status !== 409) setError(e.message)
        }
      } else {
        setCalendars(null)
      }
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function connect() {
    setBusy(true)
    setError(null)
    try {
      const { auth_url } = await api.get(
        `/calendar/authorize-url?redirect_uri=${encodeURIComponent(
          `${window.location.origin}/calendar/callback`,
        )}`,
      )
      window.location.href = auth_url
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  async function disconnect() {
    if (!confirm('Google-Konto trennen? Bestehende Spiegel-Events bleiben stehen.')) return
    setBusy(true)
    try {
      await api.post('/calendar/disconnect')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!status) {
    return (
      <div className="py-16 flex justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow">Verbindung</p>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Kalender verbinden</h1>
        <p className="text-sm text-ink/60 mt-1">
          Verbinde deinen @koenigswege.com-Google-Account. Über die native
          Google-Freigabe reingeteilte Kalender erscheinen automatisch in der Liste.
        </p>
      </div>

      {justConnected && status.connected && (
        <div className="rounded-lg bg-green-50 border-l-4 border-green-500 text-green-900 p-3 text-sm">
          Kalender erfolgreich verbunden.
        </div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 border-l-4 border-red-500 text-red-900 p-3 text-sm">
          {error}
        </div>
      )}

      {status.connected ? (
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 min-w-0">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-royal/10 text-royal shrink-0">
                <LinkIcon />
              </span>
              <div className="min-w-0">
                <div className="font-bold truncate">{status.google_email || 'Verbunden'}</div>
                <div className="text-xs text-ink/60">Verbunden · Sync aktiv</div>
              </div>
            </div>
            <button className="btn-outline btn-sm" disabled={busy} onClick={disconnect}>
              Trennen
            </button>
          </div>
        </div>
      ) : (
        <div className="card p-6 text-center space-y-4">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-royal/10 text-royal">
            <Calendar />
          </span>
          <div>
            <h3 className="font-black">Noch kein Kalender verbunden</h3>
            <p className="text-sm text-ink/60 mt-1">
              Verbinde dein Google-Konto, um Sync-Paare anzulegen.
            </p>
          </div>
          <button className="btn-primary" disabled={busy} onClick={connect}>
            {busy ? 'Weiterleitung…' : 'Google-Konto verbinden'}
          </button>
        </div>
      )}

      {status.connected && calendars && (
        <div className="space-y-3">
          <h2 className="font-black">Sichtbare Kalender</h2>
          <div className="card p-0 divide-y divide-ink/5">
            {calendars.length === 0 && (
              <div className="p-4 text-sm text-ink/50">Keine Kalender gefunden.</div>
            )}
            {calendars.map((c) => (
              <div key={c.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="h-3 w-3 rounded-full shrink-0"
                    style={{ background: c.background_color || '#2947c9' }}
                  />
                  <span className="truncate text-sm font-medium">{c.summary}</span>
                  {c.primary && <Pill tone="soft">Haupt</Pill>}
                </div>
                <span className="text-xs text-ink/50 shrink-0">
                  {ROLE_LABEL[c.access_role] || c.access_role}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card p-5 bg-royal/5 border-royal/15">
        <h3 className="font-black text-sm">So kommen private Kalender rein</h3>
        <ul className="mt-2 text-sm text-ink/70 space-y-1.5 list-disc pl-5">
          <li>
            Privaten Kalender in Google an deinen <b>@koenigswege.com</b>-Account freigeben —
            nicht hier separat einloggen.
          </li>
          <li>
            <b>Quelle</b> braucht mindestens <b>„Alle Termindetails sehen"</b> (nur „frei/gebucht"
            reicht nicht — wir brauchen Event-IDs für Idempotenz und Löschen).
          </li>
          <li>
            <b>Ziel</b> braucht <b>„Änderungen an Terminen vornehmen"</b> (Schreibrecht).
          </li>
        </ul>
      </div>
    </div>
  )
}
