import { useState, useCallback } from 'react'
import axios from 'axios'

interface ModelDownloadProps {
  onDownload: (modelName: string, revision?: string) => void
  onClose: () => void
}

interface ModelValidation {
  valid: boolean
  model_id?: string
  downloads?: number
  likes?: number
  pipeline_tag?: string
  error?: string
}

interface ModelRevisions {
  branches: string[]
  tags: string[]
  default: string | null
}

const ModelDownload = ({ onDownload, onClose }: ModelDownloadProps) => {
  const [modelName, setModelName] = useState('')
  const [revision, setRevision] = useState('')
  const [isDownloading, setIsDownloading] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const [isLoadingRevisions, setIsLoadingRevisions] = useState(false)
  const [validation, setValidation] = useState<ModelValidation | null>(null)
  const [revisions, setRevisions] = useState<ModelRevisions | null>(null)

  const validateModel = useCallback(async (name: string) => {
    if (!name || !name.includes('/')) {
      setValidation(null)
      setRevisions(null)
      return
    }

    setIsValidating(true)
    setValidation(null)
    setRevisions(null)

    try {
      const response = await axios.get(`/api/models/validate/${encodeURIComponent(name)}`)
      setValidation(response.data.data)

      if (response.data.data.valid) {
        // Load revisions
        setIsLoadingRevisions(true)
        try {
          const revResponse = await axios.get(`/api/models/revisions/${encodeURIComponent(name)}`)
          setRevisions(revResponse.data.data)
          setRevision(revResponse.data.data.default || 'main')
        } catch (err) {
          console.error('Failed to load revisions:', err)
        } finally {
          setIsLoadingRevisions(false)
        }
      }
    } catch (err) {
      setValidation({ valid: false, error: 'Failed to validate model' })
    } finally {
      setIsValidating(false)
    }
  }, [])

  const handleModelNameBlur = () => {
    validateModel(modelName.trim())
  }

  const handleDownload = () => {
    if (!modelName || !validation?.valid) return
    setIsDownloading(true)
    onDownload(modelName.trim(), revision || undefined)
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
        <div className="flex justify-between items-center p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Download Model from HuggingFace</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>
        
        <div className="p-4 space-y-4">
          {/* Model Name Input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model Name <span className="text-red-500">*</span>
            </label>
            <input 
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              onBlur={handleModelNameBlur}
              placeholder="organization/model-name"
              className={`w-full border rounded px-3 py-2 ${
                validation 
                  ? validation.valid 
                    ? 'border-green-500 bg-green-50' 
                    : 'border-red-500 bg-red-50'
                  : 'border-gray-300'
              }`}
            />
            <p className="text-xs text-gray-500 mt-1">
              Format: org/model (e.g., Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8)
            </p>

            {/* Validation Status */}
            {isValidating && (
              <p className="text-sm text-blue-600 mt-2">Validating model...</p>
            )}
            {validation && !isValidating && (
              <div className={`mt-2 p-2 rounded text-sm ${validation.valid ? 'bg-green-100' : 'bg-red-100'}`}>
                {validation.valid ? (
                  <div className="flex items-center justify-between">
                    <span className="text-green-800">Model found</span>
                    <div className="flex gap-3 text-xs text-gray-600">
                      {validation.downloads !== undefined && (
                        <span>{formatNumber(validation.downloads)} downloads</span>
                      )}
                      {validation.likes !== undefined && (
                        <span>{formatNumber(validation.likes)} likes</span>
                      )}
                      {validation.pipeline_tag && (
                        <span className="px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded">
                          {validation.pipeline_tag}
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <span className="text-red-800">{validation.error || 'Model not found'}</span>
                )}
              </div>
            )}
          </div>
          
          {/* Revision Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Revision
            </label>
            {isLoadingRevisions ? (
              <p className="text-sm text-gray-500">Loading revisions...</p>
            ) : revisions && revisions.branches.length > 0 ? (
              <select
                value={revision}
                onChange={(e) => setRevision(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2"
              >
                <optgroup label="Branches">
                  {revisions.branches.map(branch => (
                    <option key={`branch-${branch}`} value={branch}>{branch}</option>
                  ))}
                </optgroup>
                {revisions.tags.length > 0 && (
                  <optgroup label="Tags">
                    {revisions.tags.map(tag => (
                      <option key={`tag-${tag}`} value={tag}>{tag}</option>
                    ))}
                  </optgroup>
                )}
              </select>
            ) : (
              <input 
                type="text"
                value={revision}
                onChange={(e) => setRevision(e.target.value)}
                placeholder="main"
                className="w-full border border-gray-300 rounded px-3 py-2"
              />
            )}
            <p className="text-xs text-gray-500 mt-1">
              Branch or tag to download (default: main)
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 p-4 border-t bg-gray-50 rounded-b-lg">
          <button 
            onClick={onClose}
            className="dashboard-button-secondary"
          >
            Cancel
          </button>
          <button 
            onClick={handleDownload}
            disabled={isDownloading || !modelName.trim() || !validation?.valid}
            className="dashboard-button"
          >
            {isDownloading ? 'Starting Download...' : 'Download Model'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ModelDownload
