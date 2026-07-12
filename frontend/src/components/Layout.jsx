import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { Burger, Close, Help } from './ui/Icons'
import IntroModal from './IntroModal'

// Eigener Wortmarke-Auftritt in Royal-Blau (kein KW-/Fin.Co-Logo).
function Wordmark({ className = '' }) {
  return (
    <span className={`flex items-center gap-2 min-w-0 ${className}`}>
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-royal shrink-0">
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 10a8 8 0 0 1 13.7-4.5L20 8" />
          <path d="M20 14a8 8 0 0 1-13.7 4.5L4 16" />
          <path d="M20 4v4h-4M4 20v-4h4" />
        </svg>
      </span>
      <span className="text-xl font-black tracking-wordmark text-ink">Sync</span>
    </span>
  )
}

const NAV = [
  { to: '/', label: 'Sync-Paare', end: true },
  { to: '/connect', label: 'Kalender verbinden' },
]

// Aktiv = Royal-Text (Blau auf Weiss erreicht AA) + leichte Flaeche.
const navCls = ({ isActive }) =>
  `px-3 py-1.5 rounded-md text-sm font-bold transition ${
    isActive ? 'bg-royal/10 text-royal' : 'text-ink/70 hover:text-ink'
  }`

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [drawer, setDrawer] = useState(false)
  const [intro, setIntro] = useState(false)

  useEffect(() => setDrawer(false), [location.pathname])

  // Kurzanleitung beim ersten Login automatisch zeigen (pro Nutzer gemerkt).
  useEffect(() => {
    if (user && localStorage.getItem(`sync_intro_seen_${user.id}`) !== '1') {
      setIntro(true)
    }
  }, [user])

  function dismissIntro(dontShow) {
    if (dontShow && user) localStorage.setItem(`sync_intro_seen_${user.id}`, '1')
    setIntro(false)
  }

  async function onLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen flex flex-col bg-paper">
      <header className="bg-paper border-b border-royal/15 sticky top-0 z-40">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          <NavLink to="/" className="flex items-center min-w-0">
            <Wordmark />
          </NavLink>

          <nav className="hidden md:flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navCls}>
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="hidden md:flex items-center gap-2">
            {user && <span className="text-sm text-ink/60 truncate max-w-[16rem]">{user.email}</span>}
            <button
              onClick={() => setIntro(true)}
              className="p-2 rounded-md hover:bg-royal/10 text-ink/60"
              aria-label="Kurzanleitung"
              title="Kurzanleitung"
            >
              <Help className="h-5 w-5" />
            </button>
            <button onClick={onLogout} className="btn-ghost btn-sm">
              Abmelden
            </button>
          </div>

          <button
            className="md:hidden p-2 -mr-2 rounded-md hover:bg-royal/10 text-ink/80"
            onClick={() => setDrawer(true)}
            aria-label="Menü öffnen"
          >
            <Burger />
          </button>
        </div>
      </header>

      {drawer && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 md:hidden">
          <button
            className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
            aria-label="Menü schließen"
            onClick={() => setDrawer(false)}
          />
          <aside className="absolute top-0 right-0 h-full w-[85%] max-w-xs bg-paper shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-ink/10">
              <span className="text-sm font-bold truncate">{user?.email}</span>
              <button
                className="p-2 rounded-md hover:bg-royal/10 text-ink/80"
                onClick={() => setDrawer(false)}
                aria-label="Schließen"
              >
                <Close />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto py-2">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `flex items-center px-4 py-3 text-sm font-bold transition ${
                      isActive ? 'bg-royal/10 text-royal' : 'text-ink hover:bg-royal/5'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="border-t border-ink/10 p-2">
              <button
                onClick={() => {
                  setDrawer(false)
                  setIntro(true)
                }}
                className="w-full text-left px-4 py-3 text-sm font-bold rounded-md text-ink hover:bg-royal/5"
              >
                Kurzanleitung
              </button>
              <button
                onClick={onLogout}
                className="w-full text-left px-4 py-3 text-sm font-bold rounded-md text-ink hover:bg-royal/5"
              >
                Abmelden
              </button>
            </div>
          </aside>
        </div>
      )}

      <main className="flex-1">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-10">{children}</div>
      </main>

      {intro && <IntroModal onDismiss={dismissIntro} />}
    </div>
  )
}
