import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import DashboardLayout from './components/layout/DashboardLayout'
import Dashboard from './pages/Dashboard'
import Containers from './pages/Containers'
import Models from './pages/Models'
import Monitoring from './pages/Monitoring'
import ConfigEditor from './pages/ConfigEditor'
import Settings from './pages/Settings'
import Login from './pages/Login'
import LoadingSpinner from './components/common/LoadingSpinner'
import authService from './services/auth'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authService.loadUser().then((ok) => setIsAuthenticated(ok)).finally(() => setLoading(false))
    const unsub = authService.subscribe((state) => setIsAuthenticated(state.isAuthenticated))
    return unsub
  }, [])

  return (
    <Router>
      <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <Login />} />
        <Route path="*" element={
          loading ? (
            <div className="min-h-screen flex items-center justify-center bg-background-color">
              <LoadingSpinner message="Loading..." />
            </div>
          ) : isAuthenticated ? (
            <DashboardLayout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/containers" element={<Containers />} />
                <Route path="/models" element={<Models />} />
                <Route path="/monitoring" element={<Monitoring />} />
                <Route path="/config" element={<ConfigEditor />} />
                <Route path="/settings" element={<Settings />} />
              </Routes>
            </DashboardLayout>
          ) : (
            <Navigate to="/login" replace />
          )
        } />
      </Routes>
    </Router>
  )
}

export default App
