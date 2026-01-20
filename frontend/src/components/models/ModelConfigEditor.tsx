import { useState, useEffect } from 'react'
import yaml from 'js-yaml'
import { ConfigPair } from '../../types/config'

interface ModelConfigEditorProps {
  modelName: string
  config: any
  configPath: string | null
  pairs: ConfigPair[]
  onSave: (modelName: string, config: any) => void
  onAssociate: (modelName: string, configPath: string) => void
}

const ModelConfigEditor = ({ 
  modelName, 
  config, 
  configPath,
  pairs, 
  onSave, 
  onAssociate 
}: ModelConfigEditorProps) => {
  const [editedConfig, setEditedConfig] = useState<string>('')
  const [selectedConfig, setSelectedConfig] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)

  useEffect(() => {
    try {
      // Check if config is empty (new model with no config)
      const isEmpty = !config || Object.keys(config).length === 0
      
      if (isEmpty) {
        // Provide a default template for new models
        const defaultTemplate = `# vLLM Configuration for ${modelName}
model: ${modelName}
served_model_name: ${modelName.split('/').pop() || modelName}
dtype: auto
max_model_len: 8192
gpu_memory_utilization: 0.9
host: 0.0.0.0
port: 8000
`
        setEditedConfig(defaultTemplate)
      } else {
        // Convert existing config object to YAML string
        const yamlStr = yaml.dump(config, {
          indent: 2,
          lineWidth: -1,  // Don't wrap lines
          noRefs: true,
          sortKeys: false
        })
        setEditedConfig(yamlStr)
      }
      setParseError(null)
    } catch (e) {
      setEditedConfig('')
      setParseError('Failed to convert config to YAML')
    }
  }, [config, modelName])

  const validateYaml = (yamlStr: string): { valid: boolean; error?: string; parsed?: any } => {
    try {
      const parsed = yaml.load(yamlStr)
      return { valid: true, parsed }
    } catch (e: any) {
      const errorMsg = e.message || 'Invalid YAML syntax'
      // Extract line number if available
      const match = errorMsg.match(/at line (\d+)/)
      if (match) {
        return { valid: false, error: `YAML syntax error at line ${match[1]}: ${errorMsg}` }
      }
      return { valid: false, error: `YAML syntax error: ${errorMsg}` }
    }
  }

  const handleChange = (value: string) => {
    setEditedConfig(value)
    // Validate on change for real-time feedback
    const result = validateYaml(value)
    if (!result.valid) {
      setParseError(result.error || 'Invalid YAML')
    } else {
      setParseError(null)
    }
  }

  const handleSave = () => {
    const result = validateYaml(editedConfig)
    if (result.valid) {
      setParseError(null)
      onSave(modelName, result.parsed)
    } else {
      setParseError(result.error || 'Invalid YAML')
    }
  }

  const handleAssociate = () => {
    if (selectedConfig) {
      onAssociate(modelName, selectedConfig)
    }
  }

  // Loading state
  if (config === null) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-500">Loading configuration...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {pairs && pairs.length > 0 && (
        <div>
          <label className="form-label">Associate Configuration</label>
          <select 
            value={selectedConfig}
            onChange={(e) => setSelectedConfig(e.target.value)}
            className="form-select"
          >
            <option value="">Select a configuration file</option>
            {pairs.map((pair) => (
              <option key={pair.config_path} value={pair.config_path}>
                {pair.model_name} ({pair.config_path})</option>
            ))}
          </select>
          <button 
            onClick={handleAssociate}
            disabled={!selectedConfig}
            className="dashboard-button btn-sm mt-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Associate Configuration
          </button>
        </div>
      )}
      
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="form-label mb-0">Edit Configuration (YAML)</label>
          <span className={`badge ${parseError ? 'badge-red' : 'badge-green'}`}>
            {parseError ? 'Invalid' : 'Valid'}
          </span>
        </div>
        <textarea 
          value={editedConfig}
          onChange={(e) => handleChange(e.target.value)}
          className={`form-input font-mono text-sm h-80 resize-y ${
            parseError ? 'border-red-300 bg-red-50 focus:ring-red-500' : ''
          }`}
          spellCheck={false}
          placeholder="# vLLM Configuration (YAML format)
model: your-model-name
host: 0.0.0.0
port: 8000
..."
        />
        {parseError && (
          <div className="alert alert-error mt-2 text-sm font-mono p-2">
            {parseError}
          </div>
        )}
        <button 
          onClick={handleSave}
          disabled={!!parseError}
          className="dashboard-button btn-sm mt-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Save Configuration
        </button>
      </div>

      <div className="text-xs text-gray-500 space-y-1 pt-2 border-t border-gray-200">
        <p>Model: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">{modelName}</code></p>
        {configPath && (
          <p>Config path: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">{configPath}</code></p>
        )}
        <p className="text-gray-400">Note: vLLM requires YAML format for configuration files.</p>
      </div>
    </div>
  )
}

export default ModelConfigEditor
