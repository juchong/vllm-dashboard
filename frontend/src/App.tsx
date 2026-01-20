import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import DashboardLayout from './components/layout/DashboardLayout'
import Dashboard from './pages/Dashboard'
import Containers from './pages/Containers'
import Models from './pages/Models'
import Monitoring from './pages/Monitoring'
import ConfigEditor from './pages/ConfigEditor'
import Settings from './pages/Settings'

function App() {
  return (
    <Router>
      <DashboardLayout>
        <Routes>
          <Route path="" element={<Dashboard />} />
          <Route path="/containers" element={<Containers />} />
          <Route path="/models" element={<Models />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/config" element={<ConfigEditor />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </DashboardLayout>
    </Router>
  )
}

export default App
