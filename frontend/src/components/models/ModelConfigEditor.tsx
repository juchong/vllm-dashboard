import { useState, useEffect } from 'react'
import yaml from 'js-yaml'
import { ConfigPair } from '../../types/config'

interface ModelConfigEditorProps {
  modelName: string
  config: any
  pairs: ConfigPair[]
  onSave: (modelName: string, config: any) => void
  onAssociate: (modelName: string, configPath: string) => void
}

const ModelConfigEditor = ({ 
  modelName, 
  config, 
  pairs, 
  onSave, 
  onAssociate 
}: ModelConfigEditorProps) => {
  const [editedConfig, setEditedConfig] = useState<string>('')
  const [selectedConfig, setSelectedConfig] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)

  useEffect(() => {
    try {
      // Convert config object to YAML string
      const yamlStr = yaml.dump(config || {}, {
        indent: 2,
        lineWidth: -1,  // Don't wrap lines
        noRefs: true,
        sortKeys: false
      })
      setEditedConfig(yamlStr)
      setParseError(null)
    } catch (e) {
      setEditedConfig('')
      setParseError('Failed to convert config to YAML')
    }
  }, [config])

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
          <h3 className="text-sm font-medium text-gray-700 mb-2">Associate Configuration</h3>
          <select 
            value={selectedConfig}
            onChange={(e) => setSelectedConfig(e.target.value)}
            className="w-full border border-gray-300 rounded px-3 py-2"
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
            className="dashboard-button mt-2"
          >
            Associate Configuration
          </button>
        </div>
      )}
      
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-gray-700">Edit Configuration (YAML)</h3>
          <span className={`text-xs px-2 py-0.5 rounded ${parseError ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
            {parseError ? 'Invalid' : 'Valid'}
          </span>
        </div>
        <textarea 
          value={editedConfig}
          onChange={(e) => handleChange(e.target.value)}
          className={`w-full border rounded px-3 py-2 font-mono text-sm h-80 resize-y ${
            parseError ? 'border-red-300 bg-red-50' : 'border-gray-300'
          }`}
          spellCheck={false}
          placeholder="# vLLM Configuration (YAML format)
model: your-model-name
host: 0.0.0.0
port: 8000
..."
        />
        {parseError && (
          <div className="text-red-600 text-sm mt-1 font-mono bg-red-50 p-2 rounded">
            {parseError}
          </div>
        )}
        <button 
          onClick={handleSave}
          disabled={!!parseError}
          className={`dashboard-button mt-2 ${parseError ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          Save Configuration
        </button>
      </div>

      <div className="text-xs text-gray-500 space-y-1">
        <p>Configuration will be saved for model: <code className="bg-gray-100 px-1 rounded">{modelName}</code></p>
        <p className="text-gray-400">Note: vLLM requires YAML format for configuration files.</p>
      </div>
    </div>
  )
}

export default ModelConfigEditor
