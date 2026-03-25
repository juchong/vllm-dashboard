import { useState, useRef, useCallback } from 'react'
import { GPUMetric } from '../../types/monitoring'
import api from '../../services/api'

interface GPUMonitorProps {
  metrics: GPUMetric[]
  userRole?: string
}

const GPUMonitor = ({ metrics, userRole }: GPUMonitorProps) => {
  const [pendingLimits, setPendingLimits] = useState<Record<number, number>>({})
  const [saving, setSaving] = useState<Record<number, boolean>>({})
  const debounceTimers = useRef<Record<number, ReturnType<typeof setTimeout>>>({})

  const isAdmin = userRole === 'admin'

  const submitPowerLimit = useCallback(async (gpuIndex: number, watts: number) => {
    setSaving(prev => ({ ...prev, [gpuIndex]: true }))
    try {
      await api.post(`/monitoring/gpu/${gpuIndex}/power`, { limit_watts: watts })
    } catch (e: unknown) {
      console.error('Failed to set power limit', e)
    } finally {
      setSaving(prev => ({ ...prev, [gpuIndex]: false }))
      setPendingLimits(prev => {
        const next = { ...prev }
        delete next[gpuIndex]
        return next
      })
    }
  }, [])

  const handleSliderChange = useCallback((gpuIndex: number, watts: number) => {
    setPendingLimits(prev => ({ ...prev, [gpuIndex]: watts }))
    if (debounceTimers.current[gpuIndex]) clearTimeout(debounceTimers.current[gpuIndex])
    debounceTimers.current[gpuIndex] = setTimeout(() => submitPowerLimit(gpuIndex, watts), 500)
  }, [submitPowerLimit])

  const handleReset = useCallback((gpuIndex: number, defaultWatts: number) => {
    if (debounceTimers.current[gpuIndex]) clearTimeout(debounceTimers.current[gpuIndex])
    setPendingLimits(prev => ({ ...prev, [gpuIndex]: defaultWatts }))
    submitPowerLimit(gpuIndex, defaultWatts)
  }, [submitPowerLimit])

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
      <h2 className="text-lg font-semibold text-heading mb-4">GPU Status</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {metrics.map((gpu) => {
          const minW = Math.round(gpu.power.min_limit / 1000)
          const maxW = Math.round(gpu.power.max_limit / 1000)
          const defaultW = Math.round(gpu.power.default_limit / 1000)
          const currentLimitW = Math.round(gpu.power.limit / 1000)
          const displayLimitW = pendingLimits[gpu.index] ?? currentLimitW
          const hasConstraints = maxW > 0

          return (
            <div key={gpu.index} className="border border-default rounded-lg p-4 surface-secondary">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-semibold text-heading">GPU {gpu.index}</h3>
                  <p className="text-sm text-dim">{gpu.name}</p>
                </div>
                <span className={`text-2xl font-bold ${getTemperatureColor(gpu.temperature)}`}>
                  {gpu.temperature}°C
                </span>
              </div>
              
              <div className="space-y-4">
                {/* GPU Utilization */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-body">GPU Utilization</span>
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
                    <span className="text-body">VRAM</span>
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
                <div className="pt-2 border-t">
                  <div className="flex justify-between text-sm">
                    <span className="text-body">Power</span>
                    <span className="font-medium">
                      {Math.round(gpu.power.usage / 1000)}W / {displayLimitW}W
                    </span>
                  </div>

                  {isAdmin && hasConstraints && (
                    <div className="mt-2 space-y-1">
                      <input
                        type="range"
                        min={minW}
                        max={maxW}
                        value={displayLimitW}
                        onChange={(e) => handleSliderChange(gpu.index, Number(e.target.value))}
                        disabled={saving[gpu.index]}
                        className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-blue-600 bg-gray-200"
                      />
                      <div className="flex justify-between items-center text-xs text-dim">
                        <span>{minW}W</span>
                        {displayLimitW !== defaultW && (
                          <button
                            onClick={() => handleReset(gpu.index, defaultW)}
                            disabled={saving[gpu.index]}
                            className="text-blue-500 hover:text-blue-700 underline"
                          >
                            Reset to {defaultW}W
                          </button>
                        )}
                        <span>{maxW}W</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default GPUMonitor
