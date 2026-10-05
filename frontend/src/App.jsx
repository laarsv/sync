import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ConfirmProvider } from './components/ui/ConfirmDialog'
import RequireAuth from './auth/RequireAuth'
import RequireAdmin from './auth/RequireAdmin'
import Layout from './components/Layout'
import Login from './pages/Login'
import PairsPage from './pages/PairsPage'
import ConnectPage from './pages/ConnectPage'
import CalendarCallback from './pages/CalendarCallback'
import AdminPage from './pages/AdminPage'
import NotFound from './pages/NotFound'

function Shell({ children }) {
  return (
    <RequireAuth>
      <Layout>{children}</Layout>
    </RequireAuth>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ConfirmProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/calendar/callback"
              element={
                <RequireAuth>
                  <CalendarCallback />
                </RequireAuth>
              }
            />
            <Route path="/" element={<Shell><PairsPage /></Shell>} />
            <Route path="/connect" element={<Shell><ConnectPage /></Shell>} />
            <Route
              path="/admin"
              element={
                <RequireAdmin>
                  <Layout>
                    <AdminPage />
                  </Layout>
                </RequireAdmin>
              }
            />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </ConfirmProvider>
    </AuthProvider>
  )
}
