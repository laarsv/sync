import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import Spinner from '../components/ui/Spinner'
import Pill from '../components/ui/Pill'
import { formatDateTime } from '../lib/format'

function StatusPill({ u }) {
  if (u.last_status === 'never') return <span className="text-xs text-ink/50">noch nie</span>
  if (u.last_error === 'revoked') return <Pill tone="err">widerrufen</Pill>
  if (u.last_status === 'ok') return <Pill tone="ok">OK</Pill>
  return <Pill tone="err">Fehler</Pill>
}

export default function AdminPage() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/admin/overview')
      .then(setRows)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <p className="eyebrow">Admin</p>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Team-Übersicht</h1>
        <p className="text-sm text-ink/60 mt-1">
          Verbindungs- und Sync-Status aller @koenigswege.com-Nutzer.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border-l-4 border-red-500 text-red-900 p-3 text-sm">
          {error}
        </div>
      )}

      {!rows && !error && (
        <div className="py-16 flex justify-center">
          <Spinner size="lg" />
        </div>
      )}

      {rows && (
        <>
          {/* Mobile */}
          <div className="md:hidden space-y-3">
            {rows.map((u) => (
              <div key={u.id} className="card p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold truncate">{u.name || u.email}</span>
                  {u.is_admin && <Pill tone="soft">Admin</Pill>}
                </div>
                <div className="text-sm text-ink/60 truncate">{u.email}</div>
                <div className="flex flex-wrap items-center gap-2">
                  {u.connected ? (
                    <Pill tone="ok">verbunden</Pill>
                  ) : (
                    <Pill tone="err">getrennt</Pill>
                  )}
                  <span className="text-xs text-ink/60">
                    {u.active_pair_count}/{u.pair_count} Paare aktiv
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-ink/50">
                  Letzter Lauf: {formatDateTime(u.last_run_at)} <StatusPill u={u} />
                </div>
              </div>
            ))}
          </div>

          {/* Desktop */}
          <div className="hidden md:block overflow-x-auto card p-0">
            <table className="w-full text-sm">
              <thead className="text-left text-ink/60 text-xs uppercase tracking-wider">
                <tr className="border-b border-ink/10">
                  <th className="px-4 py-3">Nutzer</th>
                  <th className="px-4 py-3">Verbindung</th>
                  <th className="px-4 py-3">Paare</th>
                  <th className="px-4 py-3">Letzter Lauf</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.id} className="border-b border-ink/5 last:border-b-0">
                    <td className="px-4 py-3">
                      <div className="font-medium flex items-center gap-2">
                        {u.name || u.email}
                        {u.is_admin && <Pill tone="soft">Admin</Pill>}
                      </div>
                      <div className="text-ink/60 text-xs">
                        {u.email}
                        {u.google_email && u.google_email !== u.email
                          ? ` · Google: ${u.google_email}`
                          : ''}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {u.connected ? (
                        <Pill tone="ok">verbunden</Pill>
                      ) : (
                        <Pill tone="err">getrennt</Pill>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink/70">
                      {u.active_pair_count}/{u.pair_count} aktiv
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-ink/70 text-xs">
                        {formatDateTime(u.last_run_at)}
                      </div>
                      <div className="mt-0.5">
                        <StatusPill u={u} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
