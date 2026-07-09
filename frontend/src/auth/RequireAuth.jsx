import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Spinner from '../components/ui/Spinner'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}
