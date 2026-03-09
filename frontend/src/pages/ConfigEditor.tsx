import { useState, useEffect } from 'react'
import api from '../services/api'
import ModelConfigEditor from '../components/models/ModelConfigEditor'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'
import { useInstanceContext } from '../contexts/InstanceContext'

interface ConfigEntry {
  model_name: string
  config_path: string
}

const ConfigEditor = () => {
  const { selectedInstanceId } = useInstanceContext()
  const [configs, setConfigs] = useState<ConfigEntry[]>([])
  const [selectedEntry, setSelectedEntry] = useState<ConfigEntry | null>(null)
  const [config, setConfig] = useState<any>(null)
  const [configPath, setConfigPath] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchConfigs = async () => {
    try {
      const response = await api.get(`/config/${selectedInstanceId}/pairs`)
      setConfigs(response.data.data)
    } catch (err) {
      setError('Failed to fetch configs')
      console.error(err)
    }
  }

  const fetchConfig = async (modelName: string) => {
    setLoading(true)
    try {
      const response = await api.get(`/config/${selectedInstanceId}/model/${modelName}`)
      const data = response.data.data || {}
      setConfig(data.config || {})
      setConfigPath(data.config_path || null)
    } catch (err) {
      setError('Failed to fetch configuration')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveConfig = async (modelName: string, configData: any) => {
    await api.post(`/config/${selectedInstanceId}/save`, { model_name: modelName, config: configData })
    await fetchConfig(modelName)
    await fetchConfigs()
  }

  const handleRegenerateConfig = async (modelName: string) => {
    const response = await api.post(`/config/${selectedInstanceId}/regenerate`, { model_name: modelName })
    const data = response.data.data || {}
    setConfig(data.config || {})
    setConfigPath(data.config_path || null)
    await fetchConfigs()
  }

  useEffect(() => {
    fetchConfigs()
  }, [selectedInstanceId])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-heading">Configuration Editor</h1>

      {loading && <LoadingSpinner message="Loading configuration..." />}
      {error && <Alert type="error">Error: {error}</Alert>}

      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-heading mb-4">Model Configurations</h2>

        <div className="space-y-2">
          {configs.map((entry) => (
            <div
              key={entry.config_path}
              onClick={() => {
                setSelectedEntry(entry)
                fetchConfig(entry.model_name)
              }}
              className={`flex justify-between items-center p-3 border rounded-lg cursor-pointer surface-hover ${
                selectedEntry?.config_path === entry.config_path ? 'border-blue-500 bg-blue-50' : 'border-default'
              }`}
            >
              <div>
                <p className="font-medium">{entry.model_name}</p>
                <p className="text-sm text-body">{entry.config_path}</p>
              </div>
              <svg className="w-5 h-5 text-faint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          ))}
        </div>
      </div>

      {selectedEntry && (
        <div className="dashboard-card">
          <ModelConfigEditor
            modelName={selectedEntry.model_name}
            config={config}
            configPath={configPath}
            onSave={handleSaveConfig}
            onRegenerate={handleRegenerateConfig}
          />
        </div>
      )}
    </div>
  )
}

export default ConfigEditor
