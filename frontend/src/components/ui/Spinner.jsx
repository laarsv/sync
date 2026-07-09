export default function Spinner({ size = 'md', className = '' }) {
  const dim = size === 'lg' ? 'h-8 w-8' : size === 'sm' ? 'h-4 w-4' : 'h-6 w-6'
  return (
    <span
      role="status"
      aria-label="Lädt"
      className={`inline-block ${dim} ${className} animate-spin rounded-full border-2 border-ink/20 border-t-royal`}
    />
  )
}
