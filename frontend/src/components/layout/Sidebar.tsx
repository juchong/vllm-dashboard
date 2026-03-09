import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  HomeIcon,
  CpuChipIcon,
  CubeIcon,
  ChartBarIcon,
  Cog8ToothIcon,
  SunIcon,
  MoonIcon,
  ArrowRightOnRectangleIcon,
} from '@heroicons/react/24/outline'
import authService from '../../services/auth'
import InstanceSelector from './InstanceSelector'

function getInitialTheme(): 'dark' | 'light' {
  const stored = localStorage.getItem('theme')
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const navItems = [
  { name: 'Dashboard', path: '', icon: HomeIcon },
  { name: 'Containers', path: '/containers', icon: CpuChipIcon },
  { name: 'Models', path: '/models', icon: CubeIcon },
  { name: 'Monitoring', path: '/monitoring', icon: ChartBarIcon },
  { name: 'Settings', path: '/settings', icon: Cog8ToothIcon }
]

const Sidebar = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>(getInitialTheme)
  const [user, setUser] = useState(authService.getState().user)
  const navigate = useNavigate()

  useEffect(() => {
    const unsub = authService.subscribe((state) => setUser(state.user))
    return unsub
  }, [])

  const handleLogout = () => {
    authService.logout()
    navigate('/login')
  }

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(prev => prev === 'dark' ? 'light' : 'dark')

  return (
    <div className="w-64 bg-gray-800 text-white h-screen fixed left-0 top-0 overflow-y-auto flex flex-col">
      <div className="px-4 py-4 border-b border-gray-700 flex items-center justify-between">
        <h1 className="text-xl font-bold">vLLM Dashboard</h1>
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <SunIcon className="w-5 h-5" /> : <MoonIcon className="w-5 h-5" />}
        </button>
      </div>

      <InstanceSelector />
      <nav className="mt-2 flex-1">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              to={item.path}
              className="flex items-center px-4 py-3 text-sm font-medium hover:bg-gray-700 transition-colors"
            >
              <Icon className="w-5 h-5 mr-3" />
              {item.name}
            </Link>
          )
        })}
      </nav>
      <div className="p-4 border-t border-gray-700">
        {user && (
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-sm text-gray-400 truncate" title={user.username}>{user.username}</span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-300 hover:text-white hover:bg-gray-700 rounded-md transition-colors"
              title="Log out"
            >
              <ArrowRightOnRectangleIcon className="w-5 h-5" />
              Log out
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default Sidebar
