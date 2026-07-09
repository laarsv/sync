import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 text-center">
      <div>
        <div className="text-5xl font-black text-royal">404</div>
        <p className="mt-2 text-ink/60">Seite nicht gefunden.</p>
        <Link to="/" className="btn-primary mt-6 inline-flex">
          Zur Startseite
        </Link>
      </div>
    </div>
  )
}
