import { GPUMetric } from '../../types/monitoring'

interface GPUMonitorProps {
  metrics: GPUMetric[]
}

const GPUMonitor = ({ metrics }: GPUMonitorProps) => {
  if (metrics.length === 0) {
    return null
  }

  const formatBytes = (bytes: number) => {
    const gb = bytes / (1024 * 1024 * 1024)
    return gb.toFixed(1)
  }

  const getTemperatureColor = (temp: number) => {
    if (temp >= 80) return 'text-red-600'
    if (temp >= 70) return 'text-yellow-600'
    return 'text-green-600'
  }

  const getUtilizationColor = (util: number) => {
    if (util >= 90) return 'bg-red-500'
    if (util >= 70) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  return (
    <div className="dashboard-card">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">GPU Status</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {metrics.map((gpu) => (
          <div key={gpu.index} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="font-semibold text-gray-900">GPU {gpu.index}</h3>
                <p className="text-sm text-gray-500">{gpu.name}</p>
              </div>
              <span className={`text-2xl font-bold ${getTemperatureColor(gpu.temperature)}`}>
                {gpu.temperature}°C
              </span>
            </div>
            
            <div className="space-y-4">
              {/* GPU Utilization */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">GPU Utilization</span>
                  <span className="font-medium">{gpu.utilization.gpu}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div 
                    className={`h-3 rounded-full transition-all duration-300 ${getUtilizationColor(gpu.utilization.gpu)}`}
                    style={{ width: `${gpu.utilization.gpu}%` }}
                  />
                </div>
              </div>
              
              {/* Memory Usage */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-600">VRAM</span>
                  <span className="font-medium">
                    {formatBytes(gpu.memory.used)} / {formatBytes(gpu.memory.total)} GB ({gpu.memory.usage_percent.toFixed(0)}%)
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div 
                    className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${gpu.memory.usage_percent}%` }}
                  />
                </div>
              </div>
              
              {/* Power */}
              <div className="flex justify-between text-sm pt-2 border-t">
                <span className="text-gray-600">Power</span>
                <span className="font-medium">
                  {Math.round(gpu.power.usage / 1000)}W / {Math.round(gpu.power.limit / 1000)}W
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default GPUMonitor
