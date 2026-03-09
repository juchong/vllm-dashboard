import { createContext, useContext, ReactNode } from 'react'
import useMonitoring from '../components/hooks/useMonitoring'
import { GPUMetric, SystemMetric } from '../types/monitoring'
import { ContainerStatus } from '../types/docker'

interface MonitoringContextValue {
  gpuMetrics: GPUMetric[]
  systemMetrics: SystemMetric | null
  inferenceContainers: ContainerStatus[]
  connected: boolean
  loading: boolean
  error: string | null
}

const MonitoringContext = createContext<MonitoringContextValue | null>(null)

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const value = useMonitoring()
  return (
    <MonitoringContext.Provider value={value}>
      {children}
    </MonitoringContext.Provider>
  )
}

export function useMonitoringContext() {
  const ctx = useContext(MonitoringContext)
  if (!ctx) throw new Error('useMonitoringContext must be used within MonitoringProvider')
  return ctx
}
