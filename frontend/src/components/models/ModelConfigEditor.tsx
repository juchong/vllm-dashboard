import { useState, useEffect, useCallback } from 'react'
import yaml from 'js-yaml'
import api from '../../services/api'

interface ModelConfigEditorProps {
  modelName: string
  config: any
  configPath: string | null
  onSave: (modelName: string, config: any) => void
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

interface EnvPreview {
  model_type: string
  inherited: Record<string, string>
  inherited_sources: Record<string, string>
  overrides: Record<string, string>
  merged: Record<string, string>
}

const ModelConfigEditor = ({
  modelName,
  config,
  configPath,
  onSave,
}: ModelConfigEditorProps) => {
  const [editedConfig, setEditedConfig] = useState<string>('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const [showCliImport, setShowCliImport] = useState(false)
  const [cliInput, setCliInput] = useState('')
  const [cliPreview, setCliPreview] = useState<Record<string, any> | null>(null)

  const [activeTab, setActiveTab] = useState<'yaml' | 'env'>('yaml')
  const [envPreview, setEnvPreview] = useState<EnvPreview | null>(null)
  const [envOverrides, setEnvOverrides] = useState<Array<{ key: string; value: string }>>([])
  const [envLoading, setEnvLoading] = useState(false)

  useEffect(() => {
    try {
      const isEmpty = !config || Object.keys(config).length === 0

      if (isEmpty) {
        const defaultTemplate = `# vLLM Configuration for ${modelName}
model: ${modelName}
model_type: dense
served_model_name: ${modelName.split('/').pop() || modelName}
dtype: auto
tensor_parallel_size: 2
max_model_len: 8192
gpu_memory_utilization: 0.90
host: 0.0.0.0
port: 8000
download_dir: /root/.cache/huggingface
trust_remote_code: true
`
        setEditedConfig(defaultTemplate)
      } else {
        const yamlStr = yaml.dump(config, {
          indent: 2,
          lineWidth: -1,
          noRefs: true,
          sortKeys: false
        })
        setEditedConfig(yamlStr)

        const overrides = config.env_overrides || {}
        setEnvOverrides(
          Object.entries(overrides).map(([key, value]) => ({ key, value: String(value) }))
        )
      }
      setParseError(null)
    } catch {
      setEditedConfig('')
      setParseError('Failed to convert config to YAML')
    }
  }, [config, modelName])

  const validateYaml = (yamlStr: string): { valid: boolean; error?: string; parsed?: any } => {
    try {
      const parsed = yaml.load(yamlStr, { schema: yaml.JSON_SCHEMA })
      return { valid: true, parsed }
    } catch (e: any) {
      const errorMsg = e.message || 'Invalid YAML syntax'
      const match = errorMsg.match(/at line (\d+)/)
      if (match) {
        return { valid: false, error: `Line ${match[1]}: ${errorMsg}` }
      }
      return { valid: false, error: errorMsg }
    }
  }

  const handleChange = (value: string) => {
    setEditedConfig(value)
    const result = validateYaml(value)
    setParseError(result.valid ? null : (result.error || 'Invalid YAML'))
  }

  const handleSave = async () => {
    const result = validateYaml(editedConfig)
    if (!result.valid) {
      setParseError(result.error || 'Invalid YAML')
      return
    }

    const parsed = result.parsed || {}
    if (envOverrides.length > 0) {
      const overridesObj: Record<string, string> = {}
      for (const { key, value } of envOverrides) {
        if (key.trim()) overridesObj[key.trim()] = value
      }
      if (Object.keys(overridesObj).length > 0) {
        parsed.env_overrides = overridesObj
      }
    }

    setSaving(true)
    setSaveResult(null)
    try {
      await onSave(modelName, parsed)
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
    const result = validateYaml(editedConfig)
    const existing = result.valid && result.parsed ? result.parsed : {}
    const merged = { ...existing, ...cliPreview }
    const newYaml = yaml.dump(merged, { indent: 2, lineWidth: -1, noRefs: true, sortKeys: false })
    setEditedConfig(newYaml)
    setParseError(null)
    setCliPreview(null)
    setCliInput('')
    setShowCliImport(false)
  }

  const fetchEnvPreview = useCallback(async () => {
    if (!configPath) return
    const filename = configPath.split('/').pop()
    if (!filename) return
    setEnvLoading(true)
    try {
      const response = await api.get(`/vllm/env/preview/${filename}`)
      setEnvPreview(response.data.data)
    } catch {
      setEnvPreview(null)
    } finally {
      setEnvLoading(false)
    }
  }, [configPath])

  useEffect(() => {
    if (activeTab === 'env') fetchEnvPreview()
  }, [activeTab, fetchEnvPreview])

  const addEnvOverride = () => setEnvOverrides(prev => [...prev, { key: '', value: '' }])
  const removeEnvOverride = (idx: number) => setEnvOverrides(prev => prev.filter((_, i) => i !== idx))
  const updateEnvOverride = (idx: number, field: 'key' | 'value', val: string) => {
    setEnvOverrides(prev => prev.map((item, i) => i === idx ? { ...item, [field]: val } : item))
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
          onClick={() => setActiveTab('yaml')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'yaml'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-dim hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Configuration (YAML)
        </button>
        <button
          onClick={() => setActiveTab('env')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'env'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-dim hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          Environment Variables
        </button>
      </div>

      {activeTab === 'yaml' && (
        <div className="space-y-4">
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
                <p className="text-xs text-dim">Paste Docker CLI args (e.g. from GitHub). Lines with backslash continuations are supported.</p>
                <textarea
                  value={cliInput}
                  onChange={(e) => { setCliInput(e.target.value); setCliPreview(null) }}
                  className="form-input font-mono text-xs h-24 resize-y"
                  placeholder={"--quantization fp8 \\\n--tensor-parallel-size 2 \\\n--enable-chunked-prefill"}
                  spellCheck={false}
                />
                <div className="flex gap-2">
                  <button onClick={handleCliParse} disabled={!cliInput.trim()} className="dashboard-button btn-sm disabled:opacity-50">
                    Parse
                  </button>
                  {cliPreview && (
                    <button onClick={handleCliMerge} className="dashboard-button btn-sm bg-green-600 hover:bg-green-700">
                      Merge into YAML
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

          {/* YAML Editor */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="form-label mb-0">Edit Configuration</label>
              <span className={`badge ${parseError ? 'badge-red' : 'badge-green'}`}>
                {parseError ? 'Invalid' : 'Valid'}
              </span>
            </div>
            <textarea
              value={editedConfig}
              onChange={(e) => handleChange(e.target.value)}
              className={`form-input font-mono text-sm h-72 resize-y ${
                parseError ? 'border-red-300 bg-red-50 focus:ring-red-500' : ''
              }`}
              spellCheck={false}
              placeholder="# vLLM Configuration (YAML format)"
            />
            {parseError && (
              <div className="alert alert-error mt-2 text-sm font-mono p-2">{parseError}</div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={!!parseError || saving}
              className="dashboard-button btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'env' && (
        <div className="space-y-4">
          {envLoading ? (
            <div className="text-dim text-sm">Loading environment variables...</div>
          ) : !envPreview ? (
            <div className="text-dim text-sm">Save the configuration first to preview environment variables.</div>
          ) : (
            <>
              {/* Inherited variables */}
              <div>
                <h4 className="text-sm font-medium text-body mb-2">Inherited Variables</h4>
                <div className="surface-secondary border rounded p-3 space-y-1 max-h-48 overflow-y-auto">
                  {Object.entries(envPreview.inherited).map(([key, value]) => (
                    <div key={key} className="flex items-center text-xs font-mono">
                      <span className="text-faint w-24 shrink-0 truncate" title={envPreview.inherited_sources[key]}>
                        {envPreview.inherited_sources[key]}
                      </span>
                      <span className="text-body">{key}</span>
                      <span className="text-faint mx-1">=</span>
                      <span className="text-body">{value}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Model overrides */}
              <div>
                <h4 className="text-sm font-medium text-body mb-2">Model Overrides</h4>
                <div className="space-y-2">
                  {envOverrides.map((item, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <input
                        value={item.key}
                        onChange={(e) => updateEnvOverride(idx, 'key', e.target.value)}
                        className="form-input font-mono text-xs flex-1"
                        placeholder="KEY"
                      />
                      <span className="text-faint">=</span>
                      <input
                        value={item.value}
                        onChange={(e) => updateEnvOverride(idx, 'value', e.target.value)}
                        className="form-input font-mono text-xs flex-1"
                        placeholder="value"
                      />
                      <button
                        onClick={() => removeEnvOverride(idx)}
                        className="text-red-500 hover:text-red-700 text-sm px-1"
                        title="Remove"
                      >&times;</button>
                    </div>
                  ))}
                  <button onClick={addEnvOverride} className="text-sm text-blue-600 hover:text-blue-800">
                    + Add override
                  </button>
                </div>
              </div>

              {/* Merged preview */}
              <details className="text-xs">
                <summary className="text-sm font-medium text-body cursor-pointer mb-1">Merged Preview (what vLLM sees)</summary>
                <div className="surface-secondary border rounded p-3 space-y-0.5 max-h-48 overflow-y-auto font-mono">
                  {Object.entries({
                    ...envPreview.inherited,
                    ...Object.fromEntries(envOverrides.filter(o => o.key.trim()).map(o => [o.key, o.value]))
                  }).map(([key, value]) => (
                    <div key={key}>
                      <span className="text-body">{key}</span>
                      <span className="text-faint">=</span>
                      <span className={envOverrides.some(o => o.key === key) ? 'text-blue-600 font-medium' : 'text-body'}>{value}</span>
                    </div>
                  ))}
                </div>
              </details>

              <button
                onClick={handleSave}
                disabled={saving}
                className="dashboard-button btn-sm disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Configuration & Overrides'}
              </button>
            </>
          )}
        </div>
      )}

      <div className="text-xs text-dim space-y-1 pt-2 border-t border-default">
        <p>Model: <code className="code-inline">{modelName}</code></p>
        {configPath && (
          <p>Config: <code className="code-inline">{configPath}</code></p>
        )}
      </div>
    </div>
  )
}

export default ModelConfigEditor
