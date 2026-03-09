import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import { MonitoringProvider } from '../../contexts/MonitoringContext'
import { InstanceProvider } from '../../contexts/InstanceContext'

interface DashboardLayoutProps {
  children: ReactNode
}

const DashboardLayout = ({ children }: DashboardLayoutProps) => {
  return (
    <InstanceProvider>
      <MonitoringProvider>
        <div className="flex h-screen bg-background-color text-text-primary">
          <Sidebar />
          <main className="flex-1 ml-64 p-6 overflow-y-auto">
            {children}
          </main>
        </div>
      </MonitoringProvider>
    </InstanceProvider>
  )
}

export default DashboardLayout
