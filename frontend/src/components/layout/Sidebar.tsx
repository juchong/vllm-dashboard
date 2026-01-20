import { Link } from 'react-router-dom'
import { 
  HomeIcon, 
  CpuChipIcon, 
  CubeIcon, 
  ChartBarIcon,
  Cog8ToothIcon 
} from '@heroicons/react/24/outline'

const navItems = [
  { name: 'Dashboard', path: '', icon: HomeIcon },
  { name: 'Containers', path: '/containers', icon: CpuChipIcon },
  { name: 'Models', path: '/models', icon: CubeIcon },
  { name: 'Monitoring', path: '/monitoring', icon: ChartBarIcon },
  { name: 'Settings', path: '/settings', icon: Cog8ToothIcon }
]

const Sidebar = () => {
  return (
    <div className="w-64 bg-gray-800 text-white h-screen fixed left-0 top-0 overflow-y-auto">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-bold">vLLM Dashboard</h1>
      </div>
      
      <nav className="mt-4">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <Link 
              key={item.name}
              to={item.path}
              className={
                `flex items-center px-4 py-3 text-sm font-medium hover:bg-gray-700 transition-colors `
              }
            >
              <Icon className="w-5 h-5 mr-3" />
              {item.name}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}

export default Sidebar
