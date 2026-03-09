import { useState, useEffect } from 'react'
import yaml from 'js-yaml'

interface ModelConfigEditorProps {
  modelName: string
  config: any
  configPath: string | null
  detectedModelType?: string
  onSave: (modelName: string, config: any) => void
  onRegenerate?: (modelName: string) => Promise<void>
}

const CORE_KEYS = [
  'model',
  'served_model_name',
  'max_model_len',
  'tensor_parallel_size',
  'host',
  'download_dir',
  'vllm_image',
  'model_type',
] as const

type CoreKey = typeof CORE_KEYS[number]

interface CoreConfig {
  model: string
  served_model_name: string
  max_model_len: number
  tensor_parallel_size: number
  host: string
  download_dir: string
  vllm_image: string
  model_type: string
}

const DEFAULT_CORE: CoreConfig = {
  model: '',
  served_model_name: '',
  max_model_len: 8192,
  tensor_parallel_size: 2,
  host: '0.0.0.0',
  download_dir: '/root/.cache/huggingface',
  vllm_image: 'vllm/vllm-openai:latest',
  model_type: 'dense_full',
}

function parseCliArgs(input: string): Record<string, any> {
  const cleaned = input.replace(/\\\s*\n/g, ' ').trim()
  const firstFlag = cleaned.indexOf('--')
  const flagSection = firstFlag >= 0 ? cleaned.slice(firstFlag) : cleaned

  const tokens = flagSection.split(/\s+/).filter(Boolean)
  const result: Record<string, any> = {}
  let i = 0

  while (i < tokens.length) {
    const token = tokens[i]
    if (!token.startsWith('--')) { i++; continue }

    const key = token.slice(2).replace(/-/g, '_')
    const next = tokens[i + 1]

    if (!next || next.startsWith('--')) {
      result[key] = true
      i++
    } else {
      const num = Number(next)
      if (!isNaN(num) && next.trim() !== '') {
        result[key] = num
      } else if (next === 'true') {
        result[key] = true
      } else if (next === 'false') {
        result[key] = false
      } else {
        result[key] = next
      }
      i += 2
    }
  }
  return result
}

function splitConfig(config: any): { core: CoreConfig; advanced: Record<string, any> } {
  const core: CoreConfig = { ...DEFAULT_CORE }
  const advanced: Record<string, any> = {}

  if (!config || typeof config !== 'object') {
    return { core, advanced }
  }

  for (const [key, value] of Object.entries(config)) {
    if (key === 'env_vars' || key === 'env_overrides') continue
    if (CORE_KEYS.includes(key as CoreKey)) {
      (core as any)[key] = value
    } else {
      advanced[key] = value
    }
  }

  return { core, advanced }
}

function mergeConfig(core: CoreConfig, advanced: Record<string, any>, envVars: Array<{ key: string; value: string }>): any {
  const result: any = {}
  
  for (const key of CORE_KEYS) {
    const val = core[key]
    if (val !== undefined && val !== '' && val !== DEFAULT_CORE[key]) {
      result[key] = val
    } else if (key === 'model' || key === 'served_model_name' || key === 'host') {
      result[key] = val || DEFAULT_CORE[key]
    }
  }
  
  for (const [key, value] of Object.entries(advanced)) {
    result[key] = value
  }
  
  if (envVars.length > 0) {
    const varsObj: Record<string, string> = {}
    for (const { key, value } of envVars) {
      if (key.trim()) varsObj[key.trim()] = value
    }
    if (Object.keys(varsObj).length > 0) {
      result.env_vars = varsObj
    }
  }
  
  return result
}

const ModelConfigEditor = ({
  modelName,
  config,
  configPath,
  detectedModelType,
  onSave,
  onRegenerate,
}: ModelConfigEditorProps) => {
  const [coreConfig, setCoreConfig] = useState<CoreConfig>({ ...DEFAULT_CORE })
  const [advancedYaml, setAdvancedYaml] = useState<string>('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const [showCliImport, setShowCliImport] = useState(false)
  const [cliInput, setCliInput] = useState('')
  const [cliPreview, setCliPreview] = useState<Record<string, any> | null>(null)

  const [activeTab, setActiveTab] = useState<'core' | 'advanced' | 'env'>('core')
  const [envVars, setEnvVars] = useState<Array<{ key: string; value: string }>>([])

  useEffect(() => {
    try {
      const isEmpty = !config || Object.keys(config).length === 0
      const effectiveModelType = detectedModelType || 'dense_full'

      if (isEmpty) {
        setCoreConfig({
          ...DEFAULT_CORE,
          model: modelName,
          served_model_name: modelName.split('/').pop() || modelName,
          model_type: effectiveModelType,
        })
        setAdvancedYaml('# Model-specific parameters\ntrust_remote_code: true\n')
      } else {
        const { core, advanced } = splitConfig(config)
        if (!core.model) core.model = modelName
        if (!core.served_model_name) core.served_model_name = modelName.split('/').pop() || modelName
        if (!config.model_type && detectedModelType) {
          core.model_type = detectedModelType
        }
        setCoreConfig(core)
        
        const advYaml = Object.keys(advanced).length > 0
          ? yaml.dump(advanced, { indent: 2, lineWidth: -1, noRefs: true, sortKeys: false })
          : '# Model-specific parameters\n'
        setAdvancedYaml(advYaml)

        const vars = config.env_vars || config.env_overrides || {}
        setEnvVars(
          Object.entries(vars).map(([key, value]) => ({ key, value: String(value) }))
        )
      }
      setParseError(null)
    } catch {
      setAdvancedYaml('')
      setParseError('Failed to parse config')
    }
  }, [config, modelName, detectedModelType])

  const validateAdvancedYaml = (yamlStr: string): { valid: boolean; error?: string; parsed?: any } => {
    try {
      const parsed = yaml.load(yamlStr, { schema: yaml.JSON_SCHEMA })
      if (parsed && typeof parsed !== 'object') {
        return { valid: false, error: 'YAML must be a key-value mapping' }
      }
      return { valid: true, parsed: parsed || {} }
    } catch (e: any) {
      const errorMsg = e.message || 'Invalid YAML syntax'
      const match = errorMsg.match(/at line (\d+)/)
      if (match) {
        return { valid: false, error: `Line ${match[1]}: ${errorMsg}` }
      }
      return { valid: false, error: errorMsg }
    }
  }

  const handleAdvancedChange = (value: string) => {
    setAdvancedYaml(value)
    const result = validateAdvancedYaml(value)
    setParseError(result.valid ? null : (result.error || 'Invalid YAML'))
  }

  const updateCoreField = <K extends keyof CoreConfig>(key: K, value: CoreConfig[K]) => {
    setCoreConfig(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    const advResult = validateAdvancedYaml(advancedYaml)
    if (!advResult.valid) {
      setParseError(advResult.error || 'Invalid YAML in advanced settings')
      setActiveTab('advanced')
      return
    }

    if (!coreConfig.model.trim()) {
      setSaveResult({ type: 'error', text: 'Model path is required' })
      setActiveTab('core')
      return
    }

    const merged = mergeConfig(coreConfig, advResult.parsed || {}, envVars)

    setSaving(true)
    setSaveResult(null)
    try {
      await onSave(modelName, merged)
      setSaveResult({ type: 'success', text: 'Configuration saved' })
      setTimeout(() => setSaveResult(null), 3000)
    } catch {
      setSaveResult({ type: 'error', text: 'Failed to save' })
    } finally {
      setSaving(false)
    }
  }

  const handleCliParse = () => {
    if (!cliInput.trim()) return
    const parsed = parseCliArgs(cliInput)
    setCliPreview(parsed)
  }

  const handleCliMerge = () => {
    if (!cliPreview) return
    
    const { core: parsedCore, advanced: parsedAdvanced } = splitConfig(cliPreview)
    
    setCoreConfig(prev => {
      const updated = { ...prev }
      for (const key of CORE_KEYS) {
        if ((parsedCore as any)[key] !== DEFAULT_CORE[key]) {
          (updated as any)[key] = (parsedCore as any)[key]
        }
      }
      return updated
    })
    
    const advResult = validateAdvancedYaml(advancedYaml)
    const existingAdvanced = advResult.valid && advResult.parsed ? advResult.parsed : {}
    const mergedAdvanced = { ...existingAdvanced, ...parsedAdvanced }
    const newAdvYaml = Object.keys(mergedAdvanced).length > 0
      ? yaml.dump(mergedAdvanced, { indent: 2, lineWidth: -1, noRefs: true, sortKeys: false })
      : '# Model-specific parameters\n'
    setAdvancedYaml(newAdvYaml)
    
    setParseError(null)
    setCliPreview(null)
    setCliInput('')
    setShowCliImport(false)
  }

  const addEnvVar = () => setEnvVars(prev => [...prev, { key: '', value: '' }])
  const removeEnvVar = (idx: number) => setEnvVars(prev => prev.filter((_, i) => i !== idx))
  const updateEnvVar = (idx: number, field: 'key' | 'value', val: string) => {
    setEnvVars(prev => prev.map((item, i) => i === idx ? { ...item, [field]: val } : item))
  }

  const [regenerating, setRegenerating] = useState(false)

  const handleRegenerate = async () => {
    if (!onRegenerate) return
    if (!confirm('Regenerate configuration from model metadata?\n\nThis will replace the current config with auto-detected defaults.')) return
    setRegenerating(true)
    setSaveResult(null)
    try {
      await onRegenerate(modelName)
      setSaveResult({ type: 'success', text: 'Configuration regenerated from model metadata' })
      setTimeout(() => setSaveResult(null), 3000)
    } catch {
      setSaveResult({ type: 'error', text: 'Failed to regenerate configuration' })
    } finally {
      setRegenerating(false)
    }
  }

  if (config === null) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-dim">Loading configuration...</div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {saveResult && (
        <div className={`p-2 rounded text-sm ${
          saveResult.type === 'success'
            ? 'bg-green-50 border border-green-200 text-green-700'
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {saveResult.text}
        </div>
      )}

      {/* Tab switcher */}
      <div className="flex border-b border-default">
        <button
          onClick={() => setActiveTab('core')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'core'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-dim hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Core Settings
        </button>
        <button
          onClick={() => setActiveTab('advanced')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'advanced'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-dim hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Advanced
        </button>
        <button
          onClick={() => setActiveTab('env')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'env'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-dim hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Environment
        </button>
      </div>

      {activeTab === 'core' && (
        <div className="space-y-4">
          <p className="text-xs text-dim">Required vLLM server parameters. These are always present in the configuration.</p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="form-label">Model Path</label>
              <input
                type="text"
                value={coreConfig.model}
                onChange={(e) => updateCoreField('model', e.target.value)}
                className="form-input font-mono text-sm"
                placeholder="org/model-name"
              />
            </div>
            <div>
              <label className="form-label">Served Model Name</label>
              <input
                type="text"
                value={coreConfig.served_model_name}
                onChange={(e) => updateCoreField('served_model_name', e.target.value)}
                className="form-input text-sm"
                placeholder="Display name for API"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="form-label">Max Model Length</label>
              <input
                type="number"
                value={coreConfig.max_model_len}
                onChange={(e) => updateCoreField('max_model_len', parseInt(e.target.value) || 0)}
                className="form-input text-sm"
                min={0}
              />
              <span className="text-xs text-dim">{(coreConfig.max_model_len / 1024).toFixed(0)}K tokens</span>
            </div>
            <div>
              <label className="form-label">Tensor Parallel Size</label>
              <input
                type="number"
                value={coreConfig.tensor_parallel_size}
                onChange={(e) => updateCoreField('tensor_parallel_size', parseInt(e.target.value) || 1)}
                className="form-input text-sm"
                min={1}
                max={8}
              />
            </div>
            <div>
              <label className="form-label">Host</label>
              <input
                type="text"
                value={coreConfig.host}
                onChange={(e) => updateCoreField('host', e.target.value)}
                className="form-input font-mono text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="form-label">vLLM Image</label>
              <input
                type="text"
                value={coreConfig.vllm_image}
                onChange={(e) => updateCoreField('vllm_image', e.target.value)}
                className="form-input font-mono text-sm"
                placeholder="vllm/vllm-openai:latest"
              />
            </div>
            <div>
              <label className="form-label">Model Type</label>
              <select
                value={coreConfig.model_type}
                onChange={(e) => updateCoreField('model_type', e.target.value)}
                className="form-input text-sm"
              >
                <optgroup label="Dense">
                  <option value="dense_full">Dense (Full Precision)</option>
                  <option value="dense_fp8">Dense FP8</option>
                  <option value="dense_int8">Dense INT8</option>
                  <option value="dense_int4">Dense INT4/AWQ</option>
                </optgroup>
                <optgroup label="Mixture of Experts">
                  <option value="moe_full">MoE (Full Precision)</option>
                  <option value="moe_fp8">MoE FP8</option>
                  <option value="moe_fp4">MoE FP4</option>
                </optgroup>
              </select>
            </div>
          </div>

          <div>
            <label className="form-label">Download Directory</label>
            <input
              type="text"
              value={coreConfig.download_dir}
              onChange={(e) => updateCoreField('download_dir', e.target.value)}
              className="form-input font-mono text-sm"
            />
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="dashboard-button btn-sm disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      )}

      {activeTab === 'advanced' && (
        <div className="space-y-4">
          <p className="text-xs text-dim">Model-specific parameters (YAML). These vary by model and use case.</p>
          
          {/* CLI Import */}
          <div>
            <button
              onClick={() => setShowCliImport(!showCliImport)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {showCliImport ? '▼ Hide' : '▶ Import from CLI args'}
            </button>
            {showCliImport && (
              <div className="mt-2 p-3 surface-secondary border rounded space-y-2">
                <p className="text-xs text-dim">Paste Docker CLI args. Core params go to Core Settings, others here.</p>
                <textarea
                  value={cliInput}
                  onChange={(e) => { setCliInput(e.target.value); setCliPreview(null) }}
                  className="form-input font-mono text-xs h-24 resize-y"
                  placeholder={"--quantization fp8 \\\n--enable-chunked-prefill \\\n--trust-remote-code"}
                  spellCheck={false}
                />
                <div className="flex gap-2">
                  <button onClick={handleCliParse} disabled={!cliInput.trim()} className="dashboard-button btn-sm disabled:opacity-50">
                    Parse
                  </button>
                  {cliPreview && (
                    <button onClick={handleCliMerge} className="dashboard-button btn-sm bg-green-600 hover:bg-green-700">
                      Merge
                    </button>
                  )}
                </div>
                {cliPreview && (
                  <div className="mt-2 p-2 surface-primary border rounded text-xs font-mono space-y-0.5">
                    {Object.entries(cliPreview).map(([k, v]) => (
                      <div key={k}><span className="text-blue-700">{k}</span>: <span className="text-body">{String(v)}</span></div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Advanced YAML Editor */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="form-label mb-0">Advanced Parameters (YAML)</label>
              <span className={`badge ${parseError ? 'badge-red' : 'badge-green'}`}>
                {parseError ? 'Invalid' : 'Valid'}
              </span>
            </div>
            <textarea
              value={advancedYaml}
              onChange={(e) => handleAdvancedChange(e.target.value)}
              className={`form-input font-mono text-sm h-56 resize-y ${
                parseError ? 'border-red-300 bg-red-50 focus:ring-red-500' : ''
              }`}
              spellCheck={false}
              placeholder="# Model-specific parameters"
            />
            {parseError && (
              <div className="alert alert-error mt-2 text-sm font-mono p-2">{parseError}</div>
            )}
          </div>

          <button
            onClick={handleSave}
            disabled={!!parseError || saving}
            className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      )}

      {activeTab === 'env' && (
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-medium text-body mb-2">Environment Variables</h4>
            <p className="text-xs text-dim mb-3">
              These environment variables are passed to the vLLM container. All env vars for this model should be defined here.
            </p>
            <div className="space-y-2">
              {envVars.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    value={item.key}
                    onChange={(e) => updateEnvVar(idx, 'key', e.target.value)}
                    className="form-input font-mono text-xs flex-1"
                    placeholder="KEY"
                  />
                  <span className="text-faint">=</span>
                  <input
                    value={item.value}
                    onChange={(e) => updateEnvVar(idx, 'value', e.target.value)}
                    className="form-input font-mono text-xs flex-1"
                    placeholder="value"
                  />
                  <button
                    onClick={() => removeEnvVar(idx)}
                    className="text-red-500 hover:text-red-700 text-sm px-1"
                    title="Remove"
                  >&times;</button>
                </div>
              ))}
              <button onClick={addEnvVar} className="text-sm text-blue-600 hover:text-blue-800">
                + Add variable
              </button>
            </div>
          </div>

          {envVars.some(o => o.key.trim()) && (
            <details className="text-xs">
              <summary className="text-sm font-medium text-body cursor-pointer mb-1">Preview (what vLLM sees)</summary>
              <div className="surface-secondary border rounded p-3 space-y-0.5 max-h-48 overflow-y-auto font-mono">
                {envVars.filter(o => o.key.trim()).map(({ key, value }) => (
                  <div key={key}>
                    <span className="text-body">{key}</span>
                    <span className="text-faint">=</span>
                    <span className="text-body">{value}</span>
                  </div>
                ))}
              </div>
            </details>
          )}

          <button
            onClick={handleSave}
            disabled={saving}
            className="dashboard-button btn-sm disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      )}

      <div className="text-xs text-dim space-y-1 pt-2 border-t border-default">
        <div className="flex items-center justify-between">
          <div>
            <p>Model: <code className="code-inline">{modelName}</code></p>
            {configPath && (
              <p>Config: <code className="code-inline">{configPath}</code></p>
            )}
          </div>
          {onRegenerate && (
            <button
              onClick={handleRegenerate}
              disabled={regenerating || saving}
              className="dashboard-button-secondary btn-sm text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              title="Delete current config and regenerate from model metadata"
            >
              {regenerating ? 'Regenerating...' : 'Regenerate Config'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ModelConfigEditor
