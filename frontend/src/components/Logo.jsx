import Wordmark from './Wordmark'

// Produkt-Lockup „Mit Signatur" — bevorzugte Tool-Marke gemäß VRWB CI:
// handschriftliche Signatur (Royal, logo-clean.svg als Maske) links, Haarlinie
// als Trenner, rechts das Standalone-Wortmarken-Lockup vrwb_sync.
// Nur auf Paper (Header). Signatur ist dekorativ -> Wortmarke trägt den Namen.
export default function Logo({ className = '' }) {
  return (
    <span className={`inline-flex items-center gap-3 min-w-0 ${className}`}>
      <span
        aria-hidden="true"
        className="block shrink-0 bg-royal"
        style={{
          width: '18px',
          height: '36px',
          WebkitMask: "url('/logo-clean.svg') center / contain no-repeat",
          mask: "url('/logo-clean.svg') center / contain no-repeat",
        }}
      />
      <span aria-hidden="true" className="block shrink-0 w-px h-7 bg-ink/15" />
      <Wordmark className="text-xl" />
    </span>
  )
}
