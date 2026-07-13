import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Spinner from '../components/ui/Spinner'

export default function RequireAdmin({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Navigate to="/" replace />
  return children
}
