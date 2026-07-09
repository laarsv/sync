// Toene: soft = Royal-Tint, neutral = Ink-Tint, ok/warn/err = Status.
const TONES = {
  soft: 'bg-royal/10 text-royal',
  neutral: 'bg-ink/5 text-ink/70',
  ok: 'bg-green-100 text-green-800',
  warn: 'bg-yellow-100 text-yellow-800',
  err: 'bg-red-100 text-red-800',
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
