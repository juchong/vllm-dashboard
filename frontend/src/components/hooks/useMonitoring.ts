import { useState, useEffect, useRef, useCallback } from 'react'
import { GPUMetric, SystemMetric } from '../../types/monitoring'
import { ContainerStatus } from '../../types/docker'
import { setTimezone } from '../../utils/formatters'

interface MonitoringData {
  gpu: GPUMetric[]
  system: SystemMetric
  containers: Record<string, ContainerStatus>
  timezone?: string
  server_time?: string
}

const useMonitoring = () => {
  const [gpuMetrics, setGpuMetrics] = useState<GPUMetric[]>([])
  const [systemMetrics, setSystemMetrics] = useState<SystemMetric | null>(null)
  const [inferenceContainers, setInferenceContainers] = useState<ContainerStatus[]>([])
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    // Build WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/updates`

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        setConnected(true)
        setError(null)
        console.log('Monitoring WebSocket connected')
      }

      wsRef.current.onclose = () => {
        setConnected(false)
        console.log('Monitoring WebSocket disconnected, reconnecting...')
        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => connect(), 3000)
      }

      wsRef.current.onerror = (err) => {
        console.error('Monitoring WebSocket error:', err)
        setError('Connection error')
      }

      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          
          if (msg.type === 'monitoring_update') {
            const data: MonitoringData = msg.data
            setGpuMetrics(data.gpu || [])
            setSystemMetrics(data.system || null)
            
            // Set timezone from server
            if (data.timezone) {
              setTimezone(data.timezone)
            }
            
            // Transform containers object to array
            if (data.containers) {
              const containerArray = Object.entries(data.containers).map(
                ([name, container]: [string, any]) => ({
                  name,
                  ...container
                })
              )
              setInferenceContainers(containerArray)
            }
            setLoading(false)
          } else if (msg.type === 'error') {
            setError(msg.message)
          }
        } catch (e) {
          console.error('Failed to parse monitoring message:', e)
        }
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      setError('Failed to connect')
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connect])

  return {
    gpuMetrics,
    systemMetrics,
    inferenceContainers,
    connected,
    loading,
    error
  }
}

export default useMonitoring
