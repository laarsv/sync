import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import Pill from '../components/ui/Pill'
import Toggle from '../components/ui/Toggle'
import Select from '../components/ui/Select'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import { Arrow, Lock, Pencil, Plus, Refresh, Trash } from '../components/ui/Icons'
import { formatDateTime, formatInterval } from '../lib/format'

const DETAIL_OPTIONS = [
  { value: 'busy', label: 'Nur belegt (generischer Block)' },
  { value: 'full', label: 'Volle Details (Titel/Ort/Beschreibung)' },
]

// Google-Event-Farben (colorId -> Name/Hex).
const EVENT_COLORS = [
  { id: '1', name: 'Lavendel', hex: '#7986cb' },
  { id: '2', name: 'Salbei', hex: '#33b679' },
  { id: '3', name: 'Traube', hex: '#8e24aa' },
  { id: '4', name: 'Flamingo', hex: '#e67c73' },
  { id: '5', name: 'Banane', hex: '#f6bf26' },
  { id: '6', name: 'Mandarine', hex: '#f4511e' },
  { id: '7', name: 'Pfau', hex: '#039be5' },
  { id: '8', name: 'Graphit', hex: '#616161' },
  { id: '9', name: 'Blaubeere', hex: '#3f51b5' },
  { id: '10', name: 'Basilikum', hex: '#0b8043' },
  { id: '11', name: 'Tomate', hex: '#d50000' },
]
const colorHex = (id) => EVENT_COLORS.find((c) => c.id === id)?.hex

const EMPTY_FORM = {
  source_calendar_id: '',
  target_calendar_id: '',
  detail_level: 'busy',
  busy_title: 'Belegt',
  title_prefix: '',
  confidential: true,
  color_id: '',
  active: true,
  create_reverse: false,
}

function StatusPill({ pair }) {
  if (pair.last_status === 'ok') return <Pill tone="ok">OK</Pill>
  if (pair.last_status === 'error') return <Pill tone="err">Fehler</Pill>
  return <Pill tone="neutral">noch nie</Pill>
}

export default function PairsPage() {
  const [pairs, setPairs] = useState(null)
  const [status, setStatus] = useState(null)
  const [pollMinutes, setPollMinutes] = useState(null)
  const [calendars, setCalendars] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const [runs, setRuns] = useState(null)
  const [showRuns, setShowRuns] = useState(false)
  const pollTimer = useRef(null)
  const mountedRef = useRef(true)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null) // pair or null
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState(null)

  const calMap = useMemo(() => {
    const m = {}
    for (const c of calendars) m[c.id] = c.summary
    return m
  }, [calendars])

  const load = useCallback(async () => {
    setError(null)
    try {
      const [p, st, cfg] = await Promise.all([
        api.get('/pairs'),
        api.get('/calendar/status'),
        api.get('/config'),
      ])
      setPairs(p)
      setStatus(st)
      setPollMinutes(cfg?.poll_interval_minutes ?? null)
      if (st.connected) {
        try {
          setCalendars(await api.get('/calendar/calendars'))
        } catch {
          setCalendars([])
        }
      }
    } catch (e) {
      setError(e.message)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    load()
    // Laeuft schon ein (Hintergrund-)Sync? -> Status pollen.
    fetchSyncStatus()
      .then((st) => {
        if (mountedRef.current && st?.running) {
          setSyncing(true)
          scheduleNextPoll(false)
        }
      })
      .catch(() => {})
    return () => {
      mountedRef.current = false
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [load])

  const sourceOptions = useMemo(
    () =>
      calendars
        .filter((c) => ['owner', 'writer', 'reader'].includes(c.access_role))
        .map((c) => ({ value: c.id, label: c.summary + (c.primary ? ' (Haupt)' : '') })),
    [calendars],
  )
  const targetOptions = useMemo(
    () =>
      calendars
        .filter((c) => ['owner', 'writer'].includes(c.access_role))
        .map((c) => ({ value: c.id, label: c.summary + (c.primary ? ' (Haupt)' : '') })),
    [calendars],
  )

  function label(id, fallback) {
    return calMap[id] || fallback || id
  }

  function openNew() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormError(null)
    setModalOpen(true)
  }

  function openEdit(pair) {
    setEditing(pair)
    setForm({
      source_calendar_id: pair.source_calendar_id,
      target_calendar_id: pair.target_calendar_id,
      detail_level: pair.detail_level,
      busy_title: pair.busy_title || 'Belegt',
      title_prefix: pair.title_prefix || '',
      confidential: pair.confidential,
      color_id: pair.color_id || '',
      active: pair.active,
      create_reverse: false,
    })
    setFormError(null)
    setModalOpen(true)
  }

  async function save() {
    setFormError(null)
    if (!form.source_calendar_id || !form.target_calendar_id) {
      setFormError('Bitte Quelle und Ziel wählen.')
      return
    }
    if (form.source_calendar_id === form.target_calendar_id) {
      setFormError('Quelle und Ziel dürfen nicht identisch sein.')
      return
    }
    setSaving(true)
    const payload = {
      source_calendar_id: form.source_calendar_id,
      source_calendar_label: calMap[form.source_calendar_id] || null,
      target_calendar_id: form.target_calendar_id,
      target_calendar_label: calMap[form.target_calendar_id] || null,
      detail_level: form.detail_level,
      busy_title: form.busy_title || 'Belegt',
      title_prefix: form.title_prefix || '',
      confidential: form.confidential,
      color_id: form.color_id || '',
      active: form.active,
    }
    let reverseNote = null
    try {
      if (editing) {
        await api.patch(`/pairs/${editing.id}`, payload)
      } else {
        await api.post('/pairs', payload)
        if (form.create_reverse) {
          const rev = {
            ...payload,
            source_calendar_id: payload.target_calendar_id,
            source_calendar_label: payload.target_calendar_label,
            target_calendar_id: payload.source_calendar_id,
            target_calendar_label: payload.source_calendar_label,
          }
          try {
            await api.post('/pairs', rev)
          } catch (e2) {
            // 409 = Gegenrichtung existierte schon -> still ok; sonst Hinweis.
            if (!(e2 instanceof ApiError && e2.status === 409)) {
              reverseNote = 'Gegenrichtung nicht angelegt: ' + e2.message
            }
          }
        }
      }
      setModalOpen(false)
      await load()
      if (reverseNote) setError(reverseNote)
      // Frisch angelegt/geändert -> sofort spiegeln.
      runSync(true)
    } catch (e) {
      setFormError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(pair) {
    try {
      await api.patch(`/pairs/${pair.id}`, { active: !pair.active })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function remove(pair) {
    if (!confirm('Paar löschen? Die gespiegelten Ziel-Events werden entfernt.')) return
    try {
      await api.del(`/pairs/${pair.id}`)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  function fetchSyncStatus() {
    return api.get('/pairs/sync-status')
  }

  function scheduleNextPoll(announce) {
    if (pollTimer.current) clearTimeout(pollTimer.current)
    pollTimer.current = setTimeout(() => pollOnce(announce), 2000)
  }

  async function pollOnce(announce) {
    let st
    try {
      st = await fetchSyncStatus()
    } catch {
      if (mountedRef.current) setSyncing(false)
      return
    }
    if (!mountedRef.current) return
    if (st.running) {
      setSyncing(true)
      scheduleNextPoll(announce)
      return
    }
    // Fertig.
    setSyncing(false)
    if (announce && st.last_run) {
      const r = st.last_run
      if (r.ok) {
        setNotice(
          `Sync fertig · ${r.created} erstellt, ${r.updated} aktualisiert, ${r.deleted} gelöscht.`,
        )
      } else {
        setError('Sync mit Fehlern abgeschlossen — Details am jeweiligen Paar.')
      }
    }
    await load()
    if (showRuns) loadRuns()
  }

  async function runSync(silent = false) {
    if (!silent) {
      setNotice(null)
      setError(null)
    }
    setSyncing(true)
    try {
      // Startet den Sync im Hintergrund und kehrt sofort zurueck.
      await api.post('/pairs/sync-now')
    } catch (e) {
      setSyncing(false)
      if (e instanceof ApiError && e.status === 409) {
        setError('Kein Kalender verbunden.')
      } else {
        setError(e.message)
      }
      return
    }
    scheduleNextPoll(true)
  }

  async function loadRuns() {
    setRuns(null)
    try {
      setRuns(await api.get('/pairs/runs?limit=20'))
    } catch {
      setRuns([])
    }
  }

  function toggleRuns() {
    const next = !showRuns
    setShowRuns(next)
    if (next && runs === null) loadRuns()
  }

  if (!pairs || !status) {
    return (
      <div className="py-16 flex justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  const connected = status.connected

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="eyebrow">Kalender-Sync</p>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Sync-Paare</h1>
          <p className="text-sm text-ink/60 mt-1">
            Ein Paar spiegelt Termine von einem Quell- in einen Ziel-Kalender. Zwei
            Richtungen = zwei Paare.
          </p>
          {pollMinutes != null && (
            <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-bold text-royal">
              <Refresh className="h-3.5 w-3.5" />
              Automatischer Sync {formatInterval(pollMinutes)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-outline btn-sm"
            disabled={syncing || !connected}
            onClick={() => runSync(false)}
          >
            <Refresh className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Synchronisiert…' : 'Jetzt synchronisieren'}
          </button>
          <button className="btn-primary btn-sm" disabled={!connected} onClick={openNew}>
            <Plus className="h-4 w-4" />
            Neues Paar
          </button>
        </div>
      </div>

      {notice && (
        <div className="rounded-lg bg-green-50 border-l-4 border-green-500 text-green-900 p-3 text-sm">
          {notice}
        </div>
      )}
      {error && (
        <div className="rounded-lg bg-red-50 border-l-4 border-red-500 text-red-900 p-3 text-sm">
          {error}
        </div>
      )}

      {!connected && (
        <div className="rounded-lg bg-royal/5 border border-royal/20 p-4 text-sm flex items-center justify-between gap-3 flex-wrap">
          <span className="text-ink/70">
            Noch kein Google-Kalender verbunden — ohne Verbindung können keine Paare
            angelegt werden.
          </span>
          <Link to="/connect" className="btn-primary btn-sm">
            Kalender verbinden
          </Link>
        </div>
      )}

      {pairs.length === 0 ? (
        <EmptyState
          title="Noch keine Sync-Paare"
          action={
            connected ? (
              <button className="btn-primary" onClick={openNew}>
                <Plus className="h-4 w-4" />
                Erstes Paar anlegen
              </button>
            ) : (
              <Link to="/connect" className="btn-primary">
                Zuerst Kalender verbinden
              </Link>
            )
          }
        >
          Lege ein Paar an, um Termine zwischen zwei Kalendern zu spiegeln.
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {pairs.map((pair) => (
            <div key={pair.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap text-sm font-bold">
                    <span className="truncate max-w-[42%]">
                      {label(pair.source_calendar_id, pair.source_calendar_label)}
                    </span>
                    <Arrow className="h-4 w-4 text-royal shrink-0" />
                    <span className="truncate max-w-[42%]">
                      {label(pair.target_calendar_id, pair.target_calendar_label)}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    {pair.color_id && (
                      <span
                        className="h-3.5 w-3.5 rounded-full border border-black/10 shrink-0"
                        style={{ background: colorHex(pair.color_id) }}
                        title="Zielfarbe"
                      />
                    )}
                    <Pill tone={pair.detail_level === 'full' ? 'soft' : 'neutral'}>
                      {pair.detail_level === 'full' ? 'Volle Details' : `Busy · „${pair.busy_title}"`}
                    </Pill>
                    {pair.title_prefix && <Pill tone="soft">Tag „{pair.title_prefix}"</Pill>}
                    {pair.confidential && (
                      <span
                        className="inline-flex items-center gap-1 text-xs text-ink/50"
                        title="Vertraulich — nur du siehst Details"
                      >
                        <Lock className="h-3.5 w-3.5" />
                        Vertraulich
                      </span>
                    )}
                    <StatusPill pair={pair} />
                    <span className="text-xs text-ink/50">
                      Letzter Lauf: {formatDateTime(pair.last_run_at)}
                    </span>
                  </div>
                  {pair.last_status === 'error' && pair.last_error && (
                    <div className="mt-2 text-xs text-red-700 bg-red-50 rounded px-2 py-1 break-words">
                      {pair.last_error}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <Toggle
                    checked={pair.active}
                    onChange={() => toggleActive(pair)}
                    label="Aktiv"
                  />
                  <div className="flex items-center gap-1">
                    <button
                      className="p-1.5 rounded-md hover:bg-ink/5 text-ink/60"
                      onClick={() => openEdit(pair)}
                      aria-label="Bearbeiten"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      className="p-1.5 rounded-md hover:bg-red-50 text-red-600"
                      onClick={() => remove(pair)}
                      aria-label="Löschen"
                    >
                      <Trash className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pt-2">
        <button className="text-sm font-bold text-royal hover:underline" onClick={toggleRuns}>
          {showRuns ? 'Sync-Verlauf ausblenden' : 'Sync-Verlauf anzeigen'}
        </button>
        {showRuns && (
          <div className="mt-3 card p-0 divide-y divide-ink/5">
            {runs === null && (
              <div className="p-4 flex justify-center">
                <Spinner size="sm" />
              </div>
            )}
            {runs && runs.length === 0 && (
              <div className="p-4 text-sm text-ink/50">Noch keine Läufe.</div>
            )}
            {runs &&
              runs.map((r, i) => (
                <div key={i} className="px-4 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-wrap">
                      {r.ok ? <Pill tone="ok">OK</Pill> : <Pill tone="err">Fehler</Pill>}
                      <span className="text-ink/60">
                        {r.trigger === 'manual' ? 'Manuell' : 'Auto'}
                      </span>
                      <span className="text-ink/50 text-xs">
                        {formatDateTime(r.finished_at || r.started_at)}
                      </span>
                    </div>
                    <div className="text-xs text-ink/60 shrink-0 tabular-nums">
                      +{r.created} / ~{r.updated} / −{r.deleted}
                    </div>
                  </div>
                  {r.error === 'revoked' && (
                    <div className="mt-1 text-xs text-red-700">
                      Zugriff widerrufen — bitte neu verbinden.
                    </div>
                  )}
                  {r.error === 'not_connected' && (
                    <div className="mt-1 text-xs text-ink/50">Nicht verbunden.</div>
                  )}
                  {!r.ok && r.error && !['revoked', 'not_connected'].includes(r.error) && (
                    <div className="mt-1 text-xs text-red-700 break-words">{r.error}</div>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editing ? 'Paar bearbeiten' : 'Neues Sync-Paar'}
        footer={
          <>
            <button className="btn-outline btn-sm" onClick={() => setModalOpen(false)}>
              Abbrechen
            </button>
            <button className="btn-primary btn-sm" disabled={saving} onClick={save}>
              {saving ? 'Speichern…' : 'Speichern'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          {formError && (
            <div className="rounded-lg bg-red-50 border-l-4 border-red-500 text-red-900 p-2.5 text-sm">
              {formError}
            </div>
          )}
          <Select
            label="Quell-Kalender"
            value={form.source_calendar_id}
            onChange={(v) => setForm((f) => ({ ...f, source_calendar_id: v }))}
            options={sourceOptions}
            placeholder="Quelle wählen"
            hint="Kalender, dessen Termine gespiegelt werden."
          />
          <Select
            label="Ziel-Kalender"
            value={form.target_calendar_id}
            onChange={(v) => setForm((f) => ({ ...f, target_calendar_id: v }))}
            options={targetOptions}
            placeholder="Ziel wählen"
            hint="Nur beschreibbare Kalender (Schreibrecht nötig)."
          />
          <Select
            label="Detailstufe"
            value={form.detail_level}
            onChange={(v) => setForm((f) => ({ ...f, detail_level: v }))}
            options={DETAIL_OPTIONS}
          />
          {form.detail_level === 'busy' && (
            <div>
              <label className="field-label">Titel des Busy-Blocks</label>
              <input
                className="input"
                value={form.busy_title}
                onChange={(e) => setForm((f) => ({ ...f, busy_title: e.target.value }))}
                placeholder="Belegt"
              />
            </div>
          )}
          <div>
            <label className="field-label">Herkunfts-Tag vor dem Titel (optional)</label>
            <input
              className="input"
              value={form.title_prefix}
              maxLength={32}
              onChange={(e) => setForm((f) => ({ ...f, title_prefix: e.target.value }))}
              placeholder="(P)"
            />
            <p className="mt-1 text-xs text-ink/60">
              Wird vor jeden gespiegelten Titel gesetzt, z. B. „(P) Meeting". Leer = kein Tag.
            </p>
          </div>
          <div>
            <label className="field-label">Farbe im Ziel-Kalender</label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, color_id: '' }))}
                title="Standard (Kalenderfarbe)"
                className={`h-7 w-7 rounded-full border grid place-items-center text-xs text-ink/50 bg-paper ${
                  form.color_id === '' ? 'ring-2 ring-royal/40 border-royal' : 'border-ink/25'
                }`}
              >
                –
              </button>
              {EVENT_COLORS.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, color_id: c.id }))}
                  title={c.name}
                  style={{ background: c.hex }}
                  className={`h-7 w-7 rounded-full ${
                    form.color_id === c.id
                      ? 'ring-2 ring-offset-1 ring-ink'
                      : 'border border-black/10'
                  }`}
                />
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <span className="text-sm font-bold">Vertraulich</span>
              <p className="text-xs text-ink/60">
                Nur du siehst die Details; andere mit Kalender-Zugriff sehen „Privat".
              </p>
            </div>
            <Toggle
              checked={form.confidential}
              onChange={(v) => setForm((f) => ({ ...f, confidential: v }))}
              label="Vertraulich"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold">Aktiv</span>
            <Toggle
              checked={form.active}
              onChange={(v) => setForm((f) => ({ ...f, active: v }))}
              label="Aktiv"
            />
          </div>
          {!editing && (
            <label className="flex items-start gap-2 text-sm cursor-pointer select-none border-t border-ink/10 pt-4">
              <input
                type="checkbox"
                checked={form.create_reverse}
                onChange={(e) => setForm((f) => ({ ...f, create_reverse: e.target.checked }))}
                className="h-4 w-4 mt-0.5 rounded border-ink/30 text-royal focus:ring-royal/40"
              />
              <span>
                <span className="font-bold">Auch Gegenrichtung anlegen</span>
                <span className="text-ink/60"> — zweites Paar Ziel → Quelle mit denselben Einstellungen.</span>
              </span>
            </label>
          )}
        </div>
      </Modal>
    </div>
  )
}
