import { useState, useEffect } from 'react'
import axios from 'axios'
import ModelList from '../components/models/ModelList'
import ModelDownload from '../components/models/ModelDownload'
import ModelConfigEditor from '../components/models/ModelConfigEditor'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'
import { ModelInfo, ConfigPair } from '../types/models'

const Models = () => {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [configPairs, setConfigPairs] = useState<ConfigPair[]>([])
  const [selectedModel, setSelectedModel] = useState<string | null>(null)
  const [modelConfig, setModelConfig] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showDownload, setShowDownload] = useState(false)

  const fetchModels = async () => {
    setLoading(true)
    try {
      const response = await axios.get('/api/models/list')
      setModels(response.data.data)
    } catch (err) {
      setError('Failed to fetch models')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const fetchConfigPairs = async () => {
    try {
      const response = await axios.get('/api/config/pairs')
      setConfigPairs(response.data.data)
    } catch (err) {
      console.error('Failed to fetch config pairs:', err)
    }
  }

  const fetchModelConfig = async (modelName: string) => {
    try {
      // Don't encode slashes - FastAPI path parameter accepts them and Traefik rejects %2F
      const response = await axios.get(`/api/config/model/${modelName}`)
      setModelConfig(response.data.data)
    } catch (err) {
      console.error('Failed to fetch model config:', err)
      setModelConfig({})  // Set empty config so editor still shows
    }
  }

  const handleDownload = async (modelName: string, revision?: string) => {
    setLoading(true)
    try {
      await axios.post('/api/models/download', { model_name: modelName, revision })
      await fetchModels()
      setShowDownload(false)
    } catch (err) {
      setError('Failed to download model')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (modelPath: string) => {
    if (!confirm('Are you sure you want to delete this model?')) return
    
    setLoading(true)
    try {
      await axios.delete(`/api/models/${encodeURIComponent(modelPath)}`)
      await fetchModels()
    } catch (err) {
      setError('Failed to delete model')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleRename = async (oldPath: string, newPath: string) => {
    setLoading(true)
    try {
      await axios.post('/api/models/rename', { old_path: oldPath, new_path: newPath })
      await fetchModels()
    } catch (err) {
      setError('Failed to rename model')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleSaveConfig = async (modelName: string, config: any) => {
    setLoading(true)
    try {
      await axios.post('/api/config/save', { model_name: modelName, config })
      await fetchModelConfig(modelName)
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
    fetchModels()
    fetchConfigPairs()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">Models</h1>
        <button onClick={() => setShowDownload(true)} className="dashboard-button">Download Model</button>
      </div>

      {loading && <LoadingSpinner message="Loading models..." />}
      {error && <Alert type="error">Error: {error}</Alert>}

      <ModelList 
        models={models}
        onDelete={handleDelete}
        onRename={handleRename}
        onViewConfig={(modelName) => {
          setSelectedModel(modelName)
          setModelConfig(null)  // Reset while loading
          fetchModelConfig(modelName)
        }}
      />

      {showDownload && (
        <ModelDownload 
          onDownload={handleDownload}
          onClose={() => setShowDownload(false)}
        />
      )}

      {selectedModel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex justify-between items-center p-4 border-b">
              <h2 className="text-lg font-semibold text-gray-900">
                Configuration: {selectedModel}
              </h2>
              <button 
                onClick={() => { setSelectedModel(null); setModelConfig(null) }} 
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                &times;
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4">
              <ModelConfigEditor 
                modelName={selectedModel}
                config={modelConfig}
                pairs={configPairs}
                onSave={handleSaveConfig}
                onAssociate={handleAssociateConfig}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Models
