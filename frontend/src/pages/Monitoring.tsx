import { useMonitoringContext } from '../contexts/MonitoringContext'
import GPUMonitor from '../components/monitoring/GPUMonitor'
import SystemStats from '../components/monitoring/SystemStats'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'
import authService from '../services/auth'

const Monitoring = () => {
  const { gpuMetrics, systemMetrics, connected, loading, error } = useMonitoringContext()
  const userRole = authService.getState().user?.role

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-heading">Monitoring</h1>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {connected ? 'Live Streaming' : 'Disconnected'}
        </span>
      </div>

      {loading && <LoadingSpinner message="Connecting to monitoring service..." />}
      {error && <Alert type="error">{error}</Alert>}

      {gpuMetrics.length > 0 ? (
        <GPUMonitor metrics={gpuMetrics} userRole={userRole} />
      ) : !loading && (
        <div className="dashboard-card text-center text-dim">
          No GPU metrics available. The backend may not have GPU access.
        </div>
      )}

      {systemMetrics && <SystemStats metrics={systemMetrics} />}
    </div>
  )
}

export default Monitoring
