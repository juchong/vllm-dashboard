import { useState, useEffect } from 'react'
import axios from 'axios'
import ModelConfigEditor from '../components/models/ModelConfigEditor'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'
import { ConfigPair } from '../types/config'

const ConfigEditor = () => {
  const [configPairs, setConfigPairs] = useState<ConfigPair[]>([])
  const [selectedPair, setSelectedPair] = useState<ConfigPair | null>(null)
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchConfigPairs = async () => {
    try {
      const response = await axios.get('/api/config/pairs')
      setConfigPairs(response.data.data)
    } catch (err) {
      setError('Failed to fetch config pairs')
      console.error(err)
    }
  }

  const fetchConfig = async (modelName: string) => {
    try {
      const response = await axios.get(`/api/config/${modelName}`)
      setConfig(response.data.data)
    } catch (err) {
      setError('Failed to fetch configuration')
      console.error(err)
    }
  }

  const handleSaveConfig = async (modelName: string, config: any) => {
    setLoading(true)
    try {
      await axios.post('/api/config/save', { model_name: modelName, config })
      await fetchConfig(modelName)
    } catch (err) {
      setError('Failed to save configuration')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleAssociateConfig = async (modelName: string, configPath: string) => {
    setLoading(true)
    try {
      await axios.post('/api/config/associate', { model_name: modelName, config_path: configPath })
      await fetchConfigPairs()
    } catch (err) {
      setError('Failed to associate configuration')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConfigPairs()
  }, [])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Configuration Editor</h1>

      {loading && <LoadingSpinner message="Loading configuration..." />}
      {error && <Alert type="error">Error: {error}</Alert>}

      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Model+Configuration Pairs</h2>
        
        <div className="space-y-2">
          {configPairs.map((pair) => (
            <div 
              key={pair.config_path}
              onClick={() => {
                setSelectedPair(pair)
                fetchConfig(pair.model_name)
              }}
              className="flex justify-between items-center p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
            >
              <div>
                <p className="font-medium">{pair.model_name}</p>
                <p className="text-sm text-gray-600">{pair.config_path}</p>
              </div>
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </div>
          ))}
        </div>
      </div>

      {selectedPair && config && (
        <ModelConfigEditor 
          modelName={selectedPair.model_name}
          config={config}
          pairs={configPairs}
          onSave={handleSaveConfig}
          onAssociate={handleAssociateConfig}
        />
      )}
    </div>
  )
}

export default ConfigEditor
