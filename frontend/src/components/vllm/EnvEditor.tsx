import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

interface EnvFile {
  filename: string
  description: string
  editable: boolean
  exists: boolean
}

interface EnvEditorProps {
  onClose: () => void
}

const EnvEditor = ({ onClose }: EnvEditorProps) => {
  const [envFiles, setEnvFiles] = useState<EnvFile[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [content, setContent] = useState<string>('')
  const [originalContent, setOriginalContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const fetchEnvFiles = useCallback(async () => {
    try {
      const response = await axios.get('/api/vllm/env')
      setEnvFiles(response.data.data || [])
    } catch (err) {
      setError('Failed to fetch environment files')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchFileContent = useCallback(async (filename: string) => {
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const response = await axios.get(`/api/vllm/env/${filename}`)
      const fileContent = response.data.data?.content || ''
      setContent(fileContent)
      setOriginalContent(fileContent)
      setSelectedFile(filename)
    } catch (err) {
      setError(`Failed to load ${filename}`)
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSave = async () => {
    if (!selectedFile) return
    
    setSaving(true)
    setError(null)
    setSuccess(null)
    
    try {
      await axios.put(`/api/vllm/env/${selectedFile}`, { content })
      setOriginalContent(content)
      setSuccess(`Successfully saved ${selectedFile}`)
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to save ${selectedFile}`)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setContent(originalContent)
  }

  const hasChanges = content !== originalContent

  useEffect(() => {
    fetchEnvFiles()
  }, [fetchEnvFiles])

  // Auto-select env.hardware on load
  useEffect(() => {
    if (envFiles.length > 0 && !selectedFile) {
      const hardware = envFiles.find(f => f.filename === 'env.hardware')
      if (hardware) {
        fetchFileContent('env.hardware')
      }
    }
  }, [envFiles, selectedFile, fetchFileContent])

  const selectedFileInfo = envFiles.find(f => f.filename === selectedFile)

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Environment Configuration</h2>
          <button 
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl"
          >
            &times;
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* File List Sidebar */}
          <div className="w-64 border-r bg-gray-50 p-4 overflow-y-auto">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Environment Files</h3>
            <div className="space-y-2">
              {envFiles.map((file) => (
                <button
                  key={file.filename}
                  onClick={() => fetchFileContent(file.filename)}
                  className={`w-full text-left p-2 rounded text-sm transition-colors ${
                    selectedFile === file.filename
                      ? 'bg-blue-100 text-blue-800 border border-blue-300'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <div className="font-medium">{file.filename}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{file.description}</div>
                  {!file.editable && (
                    <span className="inline-block mt-1 px-1.5 py-0.5 text-xs bg-gray-200 text-gray-600 rounded">
                      read-only
                    </span>
                  )}
                </button>
              ))}
            </div>
            
            <div className="mt-6 p-3 bg-blue-50 rounded text-xs text-blue-800">
              <strong>How it works:</strong>
              <ul className="mt-1 space-y-1 list-disc list-inside">
                <li><code>env.hardware</code> applies to all models</li>
                <li><code>env.moe-fp8</code> applies to FP8 MoE models</li>
                <li><code>env.dense</code> applies to dense models</li>
                <li><code>env.active</code> is auto-generated when switching configs</li>
              </ul>
            </div>
          </div>

          {/* Editor Area */}
          <div className="flex-1 flex flex-col p-4 overflow-hidden">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-gray-500">Loading...</div>
              </div>
            ) : selectedFile ? (
              <>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="font-medium text-gray-900">{selectedFile}</span>
                    {hasChanges && (
                      <span className="ml-2 text-xs text-orange-600">(unsaved changes)</span>
                    )}
                  </div>
                  {selectedFileInfo?.editable && (
                    <div className="flex gap-2">
                      <button
                        onClick={handleReset}
                        disabled={!hasChanges || saving}
                        className="px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded disabled:opacity-50"
                      >
                        Reset
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={!hasChanges || saving}
                        className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  )}
                </div>

                {error && (
                  <div className="mb-2 p-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
                    {error}
                  </div>
                )}

                {success && (
                  <div className="mb-2 p-2 bg-green-50 border border-green-200 text-green-700 text-sm rounded">
                    {success}
                  </div>
                )}

                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  disabled={!selectedFileInfo?.editable}
                  className={`flex-1 w-full border rounded p-3 font-mono text-sm resize-none ${
                    selectedFileInfo?.editable 
                      ? 'border-gray-300 bg-white' 
                      : 'border-gray-200 bg-gray-50 text-gray-600'
                  }`}
                  spellCheck={false}
                  placeholder={selectedFileInfo?.editable 
                    ? "# Environment variables (KEY=VALUE format)\n# Lines starting with # are comments"
                    : "This file is auto-generated and cannot be edited directly."
                  }
                />

                <div className="mt-2 text-xs text-gray-500">
                  {selectedFileInfo?.editable ? (
                    <>Format: <code>KEY=VALUE</code> (one per line). Lines starting with <code>#</code> are comments.</>
                  ) : (
                    <>This file is generated from <code>env.hardware</code> + model-type env file when switching configurations.</>
                  )}
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Select a file from the sidebar
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50 text-xs text-gray-500">
          <strong>Note:</strong> Changes to env files will take effect on the next config switch or vLLM restart.
        </div>
      </div>
    </div>
  )
}

export default EnvEditor
