import { useEffect, useState } from 'react'
import { Close, Calendar, LinkIcon, Share, Check, Arrow } from './ui/Icons'

const STEPS = [
  {
    icon: Arrow,
    title: 'Was Sync macht',
    text: 'Sync spiegelt Termine von einem Quell- in einen Ziel-Kalender – als generischen „Belegt"-Block oder mit vollen Details. Eine Richtung = ein Paar; für beide Richtungen legst du zwei Paare an.',
  },
  {
    icon: LinkIcon,
    title: 'Google-Konto verbinden',
    text: 'Unter „Kalender verbinden" verbindest du deinen Google-Account einmalig per Login. Sync speichert nur diesen einen Zugang – verschlüsselt.',
  },
  {
    icon: Share,
    title: 'Private Kalender reinholen',
    text: 'Private Kalender nicht hier separat einloggen, sondern in Google nativ an deinen verbundenen Account freigeben. Danach erscheinen sie automatisch in der Kalenderliste.',
  },
  {
    icon: Check,
    title: 'Die richtigen Freigabe-Rechte',
    text: 'Quelle braucht mindestens „Alle Termindetails sehen" (nur „frei/gebucht" reicht nicht). Ziel braucht „Änderungen an Terminen vornehmen" (Schreibrecht).',
  },
  {
    icon: Calendar,
    title: 'Paar anlegen & fertig',
    text: 'Quelle → Ziel wählen, Detailstufe festlegen, aktivieren. Sync läuft dann automatisch alle paar Minuten; „Jetzt synchronisieren" stößt es sofort an.',
  },
]

export default function IntroModal({ onDismiss }) {
  const [dontShow, setDontShow] = useState(false)

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onDismiss(dontShow)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onDismiss, dontShow])

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center">
      <button
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        aria-label="Schließen"
        onClick={() => onDismiss(dontShow)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Willkommen bei sync"
        className="relative z-10 w-full sm:max-w-lg bg-paper rounded-t-2xl sm:rounded-2xl shadow-xl
          max-h-[92vh] flex flex-col"
      >
        {/* Header mit Royal-Flaeche (Vordergrund = Weiss) */}
        <div className="relative bg-royal text-paper px-6 pt-6 pb-5 rounded-t-2xl">
          <button
            className="absolute top-4 right-4 p-1.5 rounded-md hover:bg-paper/15 text-paper"
            onClick={() => onDismiss(dontShow)}
            aria-label="Schließen"
          >
            <Close className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-paper/15">
              <svg className="h-6 w-6 text-paper" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 10a8 8 0 0 1 13.7-4.5L20 8" />
                <path d="M20 14a8 8 0 0 1-13.7 4.5L4 16" />
                <path d="M20 4v4h-4M4 20v-4h4" />
              </svg>
            </span>
            <div>
              <div className="text-lg font-black tracking-wordmark">Willkommen bei sync</div>
              <div className="text-sm text-paper/80">In 5 Schritten erklärt</div>
            </div>
          </div>
        </div>

        <div className="px-6 py-5 overflow-y-auto space-y-4">
          {STEPS.map((s, i) => {
            const Icon = s.icon
            return (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center shrink-0">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-royal/10 text-royal font-black text-sm">
                    {i + 1}
                  </span>
                  {i < STEPS.length - 1 && <span className="w-px flex-1 bg-ink/10 mt-1" />}
                </div>
                <div className="pb-1">
                  <div className="flex items-center gap-2 font-bold">
                    <Icon className="h-4 w-4 text-royal shrink-0" />
                    {s.title}
                  </div>
                  <p className="mt-1 text-sm text-ink/70 leading-relaxed">{s.text}</p>
                </div>
              </div>
            )
          })}
        </div>

        <div className="px-6 py-4 border-t border-ink/10 flex items-center justify-between gap-3 flex-wrap">
          <label className="flex items-center gap-2 text-sm text-ink/70 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(e) => setDontShow(e.target.checked)}
              className="h-4 w-4 rounded border-ink/30 text-royal focus:ring-royal/40"
            />
            Nicht mehr anzeigen
          </label>
          <button className="btn-primary btn-sm" onClick={() => onDismiss(dontShow)}>
            Los geht’s
          </button>
        </div>
      </div>
    </div>
  )
}
