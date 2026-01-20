import { SystemMetric } from '../../types/monitoring'

interface SystemStatsProps {
  metrics: SystemMetric
}

const SystemStats = ({ metrics }: SystemStatsProps) => {
  return (
    <div className="dashboard-card">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">System Statistics</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-2">CPU</h3>
          <p className="text-2xl font-bold" style={{ color: metrics.cpu.percent > 80 ? '#ef4444' : '#10b981' }}>
            {metrics.cpu.percent}%
          </p>
          <p className="text-sm text-gray-600">Usage</p>
        </div>
        
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-2">Memory</h3>
          <p className="text-2xl font-bold" style={{ color: metrics.memory.percent > 80 ? '#ef4444' : '#10b981' }}>
            {metrics.memory.percent}%
          </p>
          <p className="text-sm text-gray-600">
            {Math.round(metrics.memory.used / 1024 / 1024)}GB / {Math.round(metrics.memory.total / 1024 / 1024)}GB
          </p>
        </div>
        
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-2">Disk</h3>
          <p className="text-2xl font-bold" style={{ color: metrics.disk.percent > 80 ? '#ef4444' : '#10b981' }}>
            {metrics.disk.percent}%
          </p>
          <p className="text-sm text-gray-600">
            {Math.round(metrics.disk.used / 1024 / 1024)}GB / {Math.round(metrics.disk.total / 1024 / 1024)}GB
          </p>
        </div>
        
        <div className="border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-2">CPU Cores</h3>
          <p className="text-2xl font-bold">
            {metrics.cpu.count}
          </p>
          <p className="text-sm text-gray-600">Total</p>
        </div>
      </div>
    </div>
  )
}

export default SystemStats
