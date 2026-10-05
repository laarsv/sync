import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Check } from './Icons'

// Custom-Dropdown (kein natives <select>). Tastaturbedienbar.
export default function Select({
  label,
  value,
  onChange,
  options = [],
  placeholder = 'Bitte wählen',
  disabled = false,
  hint,
  error,
}) {
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const rootRef = useRef(null)

  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    function onDocClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  useEffect(() => {
    if (open) {
      const idx = options.findIndex((o) => o.value === value)
      setActiveIdx(idx >= 0 ? idx : 0)
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  function choose(idx) {
    const opt = options[idx]
    if (!opt) return
    onChange(opt.value)
    setOpen(false)
  }

  function onKeyDown(e) {
    if (disabled) return
    if (!open && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
      e.preventDefault()
      setOpen(true)
      return
    }
    if (!open) return
    if (e.key === 'Escape') {
      setOpen(false)
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(activeIdx)
    }
  }

  return (
    <div className="block text-sm">
      {label && <span className="field-label">{label}</span>}
      <div className="relative" ref={rootRef}>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => !disabled && setOpen((o) => !o)}
          onKeyDown={onKeyDown}
          className={`w-full flex items-center justify-between gap-2 border rounded-lg px-3 py-1.5
            min-h-[44px] sm:min-h-[38px] text-base bg-paper text-left outline-none transition
            focus:border-royal focus:ring-2 focus:ring-royal/30
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? 'border-neg' : 'border-ink/20'}`}
        >
          <span className={`truncate ${selected ? 'text-ink' : 'text-ink/50'}`}>
            {selected ? selected.label : placeholder}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 text-ink/60" />
        </button>

        {open && (
          <ul
            role="listbox"
            className="absolute z-50 mt-1 w-full max-h-64 overflow-auto rounded-lg border
              border-ink/10 bg-paper shadow-lg py-1"
          >
            {options.length === 0 && (
              <li className="px-3 py-2 text-sm text-ink/50">Keine Optionen</li>
            )}
            {options.map((opt, idx) => {
              const isSelected = opt.value === value
              const isActive = idx === activeIdx
              return (
                <li
                  key={opt.value}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActiveIdx(idx)}
                  onClick={() => choose(idx)}
                  className={`px-3 py-2 text-sm cursor-pointer flex items-center justify-between gap-2
                    ${isSelected ? 'bg-royal/15 text-ink' : isActive ? 'bg-royal/10 text-ink' : 'text-ink'}`}
                >
                  <span className="truncate">{opt.label}</span>
                  {isSelected && <Check className="h-4 w-4 shrink-0 text-royal" />}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      {error ? (
        <span className="block text-xs text-neg mt-1">{error}</span>
      ) : hint ? (
        <span className="block text-xs text-ink/60 mt-1">{hint}</span>
      ) : null}
    </div>
  )
}
