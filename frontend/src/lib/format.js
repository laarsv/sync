export function formatInterval(minutes) {
  if (!minutes || minutes < 1) return 'automatisch'
  if (minutes === 1) return 'jede Minute'
  if (minutes === 60) return 'jede Stunde'
  if (minutes % 60 === 0) return `alle ${minutes / 60} Stunden`
  return `alle ${minutes} Minuten`
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
