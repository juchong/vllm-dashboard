import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import api from '../services/api'

export interface Instance {
  id: string
  display_name: string
  container_name: string
  proxy_container_name: string
  port: number
  proxy_port: number
  subdomain: string
  managed_by: string
  gpu_device_ids: string[] | null
  has_api_key?: boolean
  expose_port?: boolean
  labels?: Record<string, string>
  vllm_status?: { status: string; running: boolean }
  proxy_status?: { status: string; running: boolean }
}

interface InstanceContextType {
  instances: Instance[]
  selectedInstance: Instance | null
  selectedInstanceId: string
  setSelectedInstanceId: (id: string) => void
  loading: boolean
  refreshInstances: () => Promise<void>
}

const InstanceContext = createContext<InstanceContextType | null>(null)

const STORAGE_KEY = 'vllm_selected_instance'

export function InstanceProvider({ children }: { children: ReactNode }) {
  const [instances, setInstances] = useState<Instance[]>([])
  const [selectedInstanceId, setSelectedInstanceIdState] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) || 'default'
  )
  const [loading, setLoading] = useState(true)

  const refreshInstances = useCallback(async () => {
    try {
      const res = await api.get('/instances')
      setInstances(res.data.data || [])
    } catch {
      setInstances([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshInstances()
    const interval = setInterval(refreshInstances, 15000)
    return () => clearInterval(interval)
  }, [refreshInstances])

  const setSelectedInstanceId = useCallback((id: string) => {
    setSelectedInstanceIdState(id)
    localStorage.setItem(STORAGE_KEY, id)
  }, [])

  const selectedInstance = instances.find(i => i.id === selectedInstanceId) || instances[0] || null

  useEffect(() => {
    if (instances.length > 0 && !instances.find(i => i.id === selectedInstanceId)) {
      setSelectedInstanceId(instances[0].id)
    }
  }, [instances, selectedInstanceId, setSelectedInstanceId])

  return (
    <InstanceContext.Provider value={{
      instances,
      selectedInstance,
      selectedInstanceId: selectedInstance?.id || 'default',
      setSelectedInstanceId,
      loading,
      refreshInstances,
    }}>
      {children}
    </InstanceContext.Provider>
  )
}

export function useInstanceContext() {
  const ctx = useContext(InstanceContext)
  if (!ctx) throw new Error('useInstanceContext must be used within InstanceProvider')
  return ctx
}
