import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import EnvEditor from './EnvEditor'

interface VLLMConfig {
  filename: string
  name: string
  model: string
  model_type: string
  max_model_len: number
  tensor_parallel_size: number
}

interface VLLMStatus {
  status: string
  running: boolean
  id?: string
  health?: string
  error?: string
}

interface ActiveConfig {
  config: any
  filename: string | null
  model_type: string
}

const ConfigSwitcher = () => {
  const [configs, setConfigs] = useState<VLLMConfig[]>([])
  const [activeConfig, setActiveConfig] = useState<ActiveConfig | null>(null)
  const [vllmStatus, setVllmStatus] = useState<VLLMStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showEnvEditor, setShowEnvEditor] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [configsRes, activeRes, statusRes] = await Promise.all([
        axios.get('/api/vllm/configs'),
        axios.get('/api/vllm/active'),
        axios.get('/api/vllm/status'),
      ])
      
      setConfigs(configsRes.data.data || [])
      setActiveConfig(activeRes.data.data)
      setVllmStatus(statusRes.data.data)
      setError(null)
    } catch (err) {
      setError('Failed to fetch vLLM configuration')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    // Refresh status every 10 seconds
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleSwitch = async (configFilename: string) => {
    if (switching) return
    
    const config = configs.find(c => c.filename === configFilename)
    if (!config) return
    
    if (!confirm(`Switch to ${config.name}?\n\nThis will restart the vLLM server and may take a few minutes.`)) {
      return
    }
    
    setSwitching(true)
    setError(null)
    
    try {
      await axios.post('/api/vllm/switch', { config_filename: configFilename })
      // Wait a moment for container to start recreating
      await new Promise(resolve => setTimeout(resolve, 2000))
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to switch configuration')
    } finally {
      setSwitching(false)
    }
  }

  const handleRestart = async () => {
    if (switching) return
    
    if (!confirm('Restart vLLM server?')) return
    
    setSwitching(true)
    try {
      await axios.post('/api/vllm/restart')
      await new Promise(resolve => setTimeout(resolve, 2000))
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to restart')
    } finally {
      setSwitching(false)
    }
  }

  const handleStop = async () => {
    if (switching) return
    
    if (!confirm('Stop vLLM server?')) return
    
    setSwitching(true)
    try {
      await axios.post('/api/vllm/stop')
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to stop')
    } finally {
      setSwitching(false)
    }
  }

  const handleStart = async () => {
    if (switching) return
    
    setSwitching(true)
    try {
      await axios.post('/api/vllm/start')
      await fetchData()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start')
    } finally {
      setSwitching(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-100 text-green-800'
      case 'exited': return 'bg-red-100 text-red-800'
      case 'restarting': return 'bg-yellow-100 text-yellow-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return 'text-green-600'
      case 'unhealthy': return 'text-red-600'
      case 'starting': return 'text-yellow-600'
      default: return 'text-gray-600'
    }
  }

  if (loading) {
    return (
      <div className="dashboard-card">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-3 text-gray-600">Loading configurations...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <div className="dashboard-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">vLLM Server Status</h2>
          <div className="flex items-center gap-2">
            {vllmStatus && (
              <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getStatusColor(vllmStatus.status)}`}>
                {vllmStatus.status}
              </span>
            )}
            {vllmStatus?.health && vllmStatus.health !== 'unknown' && (
              <span className={`text-xs ${getHealthColor(vllmStatus.health)}`}>
                ({vllmStatus.health})
              </span>
            )}
          </div>
        </div>

        {activeConfig?.config && (
          <div className="bg-gray-50 rounded-lg p-4 mb-4">
            <div className="text-sm text-gray-500 mb-1">Active Model</div>
            <div className="font-semibold text-gray-900">{activeConfig.config.served_model_name}</div>
            <div className="text-sm text-gray-600 mt-1">{activeConfig.config.model}</div>
            <div className="flex flex-wrap gap-4 mt-2 text-xs text-gray-500">
              <span>Context: {(activeConfig.config.max_model_len / 1024).toFixed(0)}K</span>
              <span>TP: {activeConfig.config.tensor_parallel_size}</span>
              <span>Type: {activeConfig.model_type}</span>
            </div>
          </div>
        )}

        <div className="flex gap-2">
          {vllmStatus?.running ? (
            <>
              <button 
                onClick={handleRestart}
                disabled={switching}
                className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {switching ? 'Working...' : 'Restart'}
              </button>
              <button 
                onClick={handleStop}
                disabled={switching}
                className="dashboard-button-danger btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Stop
              </button>
            </>
          ) : (
            <button 
              onClick={handleStart}
              disabled={switching}
              className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {switching ? 'Starting...' : 'Start'}
            </button>
          )}
          <button 
            onClick={() => setShowEnvEditor(true)}
            className="dashboard-button-secondary btn-sm ml-auto"
          >
            Environment
          </button>
        </div>
      </div>

      {/* Environment Editor Modal */}
      {showEnvEditor && (
        <EnvEditor onClose={() => setShowEnvEditor(false)} />
      )}

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {/* Available Configurations */}
      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Available Configurations</h2>
        
        {configs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            No configurations found. Add YAML config files to your vLLM configs directory.
          </div>
        ) : (
          <div className="space-y-3">
            {configs.map((config) => {
              const isActive = activeConfig?.filename === config.filename
              
              return (
                <div 
                  key={config.filename}
                  className={`border rounded-lg p-4 transition-colors ${
                    isActive 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-gray-900">{config.name}</h3>
                        {isActive && (
                          <span className="badge bg-blue-500 text-white">Active</span>
                        )}
                        <span className={`badge ${
                          config.model_type === 'moe_fp8' ? 'badge-purple' : 'badge-gray'
                        }`}>
                          {config.model_type}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600 mt-1 truncate">{config.model}</div>
                      <div className="flex gap-4 mt-2 text-xs text-gray-500">
                        <span>Context: {(config.max_model_len / 1024).toFixed(0)}K</span>
                        <span>TP: {config.tensor_parallel_size}</span>
                        <span className="text-gray-400">{config.filename}</span>
                      </div>
                    </div>
                    
                    {!isActive && (
                      <button
                        onClick={() => handleSwitch(config.filename)}
                        disabled={switching}
                        className="dashboard-button btn-sm ml-4 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {switching ? 'Switching...' : 'Activate'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {switching && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-sm mx-4">
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-700">
                Switching configuration...<br/>
                <span className="text-sm text-gray-500">This may take a few minutes</span>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConfigSwitcher
