// Custom-Switch. An = Royal-Flaeche.
export default function Toggle({ checked, onChange, disabled = false, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition
        focus:outline-none focus:ring-2 focus:ring-royal/40 disabled:opacity-50
        ${checked ? 'bg-royal' : 'bg-ink/20'}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-paper shadow transition
          ${checked ? 'translate-x-5' : 'translate-x-0.5'}`}
      />
    </button>
  )
}
