import { useState } from 'react'
import useMonitoring from '../components/hooks/useMonitoring'
import ContainerLogs from '../components/containers/ContainerLogs'
import GPUMonitor from '../components/monitoring/GPUMonitor'
import SystemStats from '../components/monitoring/SystemStats'
import ConfigSwitcher from '../components/vllm/ConfigSwitcher'
import LoadingSpinner from '../components/common/LoadingSpinner'

const Dashboard = () => {
  const { gpuMetrics, systemMetrics, connected, loading, error } = useMonitoring()
  const [showLogs, setShowLogs] = useState(false)
  const [selectedContainer, setSelectedContainer] = useState('')

  const handleViewLogs = (containerName: string) => {
    setSelectedContainer(containerName)
    setShowLogs(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => handleViewLogs('vllm')}
            className="dashboard-button-secondary text-sm"
          >
            View Logs
          </button>
          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>

      {loading && <LoadingSpinner message="Connecting to monitoring..." />}
      {error && <div className="text-red-600 p-3 bg-red-50 rounded">Error: {error}</div>}

      {/* Model Configuration Switcher */}
      <ConfigSwitcher />

      {/* GPU and System Monitoring */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GPUMonitor metrics={gpuMetrics} />
        {systemMetrics && <SystemStats metrics={systemMetrics} />}
      </div>

      {showLogs && (
        <ContainerLogs 
          containerName={selectedContainer}
          onClose={() => setShowLogs(false)}
        />
      )}
    </div>
  )
}

export default Dashboard
