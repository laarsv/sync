// Toene: soft = Royal-Tint, neutral = Ink-Tint, ok/warn/err = Status.
const TONES = {
  soft: 'bg-royal/10 text-royal',
  neutral: 'bg-ink/5 text-ink/70',
  ok: 'bg-pos-tint text-pos',
  warn: 'bg-warn-tint text-warn',
  err: 'bg-neg-tint text-neg',
}

export default function Pill({ tone = 'neutral', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
        TONES[tone] || TONES.neutral
      } ${className}`}
    >
      {children}
    </span>
  )
}
