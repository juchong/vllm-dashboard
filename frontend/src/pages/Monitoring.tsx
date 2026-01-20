import useMonitoring from '../components/hooks/useMonitoring'
import GPUMonitor from '../components/monitoring/GPUMonitor'
import SystemStats from '../components/monitoring/SystemStats'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'

const Monitoring = () => {
  const { gpuMetrics, systemMetrics, connected, loading, error } = useMonitoring()

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Monitoring</h1>
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm ${connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {connected ? 'Live Streaming' : 'Disconnected'}
        </span>
      </div>

      {loading && <LoadingSpinner message="Connecting to monitoring service..." />}
      {error && <Alert type="error">{error}</Alert>}

      {gpuMetrics.length > 0 ? (
        <GPUMonitor metrics={gpuMetrics} />
      ) : !loading && (
        <div className="dashboard-card text-center text-gray-500">
          No GPU metrics available. The backend may not have GPU access.
        </div>
      )}

      {systemMetrics && <SystemStats metrics={systemMetrics} />}
    </div>
  )
}

export default Monitoring
