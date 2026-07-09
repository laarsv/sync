import { useEffect } from 'react'
import { Close } from './Icons'

export default function Modal({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <button
        className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
        aria-label="Schließen"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="relative z-10 w-full sm:max-w-lg bg-paper rounded-t-2xl sm:rounded-2xl shadow-xl
          max-h-[92vh] flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink/10">
          <h2 className="text-lg font-black">{title}</h2>
          <button
            className="p-1.5 rounded-md hover:bg-ink/5 text-ink/70"
            onClick={onClose}
            aria-label="Schließen"
          >
            <Close className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto">{children}</div>
        {footer && (
          <div className="px-5 py-4 border-t border-ink/10 flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
