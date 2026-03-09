import { useState } from 'react'
import { useMonitoringContext } from '../contexts/MonitoringContext'
import { useInstanceContext } from '../contexts/InstanceContext'
import ContainerLogs from '../components/containers/ContainerLogs'
import GPUMonitor from '../components/monitoring/GPUMonitor'
import SystemStats from '../components/monitoring/SystemStats'
import ConfigSwitcher from '../components/vllm/ConfigSwitcher'
import LoadingSpinner from '../components/common/LoadingSpinner'

const Dashboard = () => {
  const { gpuMetrics, systemMetrics, connected, loading, error } = useMonitoringContext()
  const { selectedInstance } = useInstanceContext()
  const [showLogs, setShowLogs] = useState(false)
  const [selectedContainer, setSelectedContainer] = useState('')

  const handleViewLogs = (containerName: string) => {
    setSelectedContainer(containerName)
    setShowLogs(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-2">
        <h1 className="text-2xl font-bold text-heading">Dashboard</h1>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => handleViewLogs(selectedInstance?.container_name || 'vllm')}
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
      {error && <div className="alert alert-error">Error: {error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GPUMonitor metrics={gpuMetrics} />
        {systemMetrics && <SystemStats metrics={systemMetrics} />}
      </div>

      <ConfigSwitcher />

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
