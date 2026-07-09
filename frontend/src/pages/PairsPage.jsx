import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import Pill from '../components/ui/Pill'
import Toggle from '../components/ui/Toggle'
import Select from '../components/ui/Select'
import Modal from '../components/ui/Modal'
import EmptyState from '../components/ui/EmptyState'
import { Arrow, Pencil, Plus, Refresh, Trash } from '../components/ui/Icons'
import { formatDateTime } from '../lib/format'

const DETAIL_OPTIONS = [
  { value: 'busy', label: 'Nur belegt (generischer Block)' },
  { value: 'full', label: 'Volle Details (Titel/Ort/Beschreibung)' },
]

const EMPTY_FORM = {
  source_calendar_id: '',
  target_calendar_id: '',
  detail_level: 'busy',
  busy_title: 'Belegt',
  active: true,
}

function StatusPill({ pair }) {
  if (pair.last_status === 'ok') return <Pill tone="ok">OK</Pill>
  if (pair.last_status === 'error') return <Pill tone="err">Fehler</Pill>
  return <Pill tone="neutral">noch nie</Pill>
}

export default function PairsPage() {
  const [pairs, setPairs] = useState(null)
  const [status, setStatus] = useState(null)
  const [calendars, setCalendars] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [syncing, setSyncing] = useState(false)

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
      const [p, st] = await Promise.all([api.get('/pairs'), api.get('/calendar/status')])
      setPairs(p)
      setStatus(st)
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
    load()
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
      active: pair.active,
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
      active: form.active,
    }
    try {
      if (editing) {
        await api.patch(`/pairs/${editing.id}`, payload)
      } else {
        await api.post('/pairs', payload)
      }
      setModalOpen(false)
      await load()
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

  async function runSync(silent = false) {
    setSyncing(true)
    if (!silent) setNotice(null)
    try {
      const r = await api.post('/pairs/sync-now')
      setNotice(
        `Sync fertig · ${r.created} erstellt, ${r.updated} aktualisiert, ${r.deleted} gelöscht.`,
      )
      await load()
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError('Kein Kalender verbunden.')
      } else {
        setError(e.message)
      }
    } finally {
      setSyncing(false)
    }
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
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-outline btn-sm"
            disabled={syncing || !connected}
            onClick={() => runSync(false)}
          >
            <Refresh className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            Jetzt synchronisieren
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
                    <Pill tone={pair.detail_level === 'full' ? 'soft' : 'neutral'}>
                      {pair.detail_level === 'full' ? 'Volle Details' : `Busy · „${pair.busy_title}"`}
                    </Pill>
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
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold">Aktiv</span>
            <Toggle
              checked={form.active}
              onChange={(v) => setForm((f) => ({ ...f, active: v }))}
              label="Aktiv"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
