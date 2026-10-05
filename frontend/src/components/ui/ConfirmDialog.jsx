import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from 'react'

// Eigener Bestätigungsdialog statt window.confirm.
// Natives <dialog> mit showModal(): Fokus bleibt im Dialog, Esc schließt (= Abbrechen),
// der Fokus kehrt zum Auslöser zurück. Klick neben den Dialog schließt NICHT.
//
//   const confirm = useConfirm()
//   if (!(await confirm({ title: 'Paar löschen?', message: '…', confirmLabel: 'Löschen', danger: true }))) return
//
// `danger` zeigt die bestätigende Aktion als Danger-Button; initialer Fokus liegt immer auf „Abbrechen“.

const ConfirmContext = createContext(null)

export function useConfirm() {
  const confirm = useContext(ConfirmContext)
  if (!confirm) throw new Error('useConfirm muss innerhalb von <ConfirmProvider> stehen')
  return confirm
}

export function ConfirmProvider({ children }) {
  // `seq` zählt Anfragen, damit der Effekt auch bei einer zweiten Anfrage reagiert.
  const [request, setRequest] = useState({ seq: 0, options: {} })
  const dialogRef = useRef(null)
  const cancelRef = useRef(null)
  const openerRef = useRef(null)
  const resolverRef = useRef(null)
  const descId = useId()

  const confirm = useCallback((options = {}) => {
    return new Promise((resolve) => {
      // Ein noch offener Dialog gilt als abgebrochen.
      resolverRef.current?.(false)
      resolverRef.current = resolve
      if (!dialogRef.current?.open) openerRef.current = document.activeElement
      setRequest((r) => ({ seq: r.seq + 1, options }))
    })
  }, [])

  // Öffnen erst nach dem Rendern, damit Titel (aria-label) und Text schon stimmen.
  useEffect(() => {
    const dialog = dialogRef.current
    if (request.seq === 0 || !dialog || dialog.open) return
    dialog.returnValue = ''
    dialog.showModal()
    cancelRef.current?.focus()
  }, [request.seq])

  // Wird vom <dialog> bei jedem Schließen ausgelöst: Button (returnValue) oder Esc ('').
  function onClose() {
    const ok = dialogRef.current?.returnValue === 'ok'
    resolverRef.current?.(ok)
    resolverRef.current = null
    const opener = openerRef.current
    openerRef.current = null
    // Browser stellen den Fokus meist selbst wieder her; hier zur Sicherheit.
    if (opener && document.contains(opener) && typeof opener.focus === 'function') opener.focus()
  }

  // Beim Abbau des Providers kein hängendes Promise zurücklassen.
  useEffect(() => () => resolverRef.current?.(false), [])

  const {
    title = 'Bist du sicher?',
    message,
    confirmLabel = 'Bestätigen',
    cancelLabel = 'Abbrechen',
    danger = false,
  } = request.options

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <dialog
        ref={dialogRef}
        aria-modal="true"
        aria-label={title}
        aria-describedby={message ? descId : undefined}
        onClose={onClose}
        className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-2xl border border-ink/10 bg-paper p-0
          text-ink shadow-2 backdrop:bg-ink/25"
      >
        <form method="dialog" className="p-5 sm:p-6">
          <h2 className="text-lg font-black">{title}</h2>
          {message && (
            <p id={descId} className="mt-2 text-sm text-ink/70">
              {message}
            </p>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <button ref={cancelRef} type="submit" value="cancel" className="btn-outline">
              {cancelLabel}
            </button>
            <button type="submit" value="ok" className={danger ? 'btn-danger' : 'btn-primary'}>
              {confirmLabel}
            </button>
          </div>
        </form>
      </dialog>
    </ConfirmContext.Provider>
  )
}
