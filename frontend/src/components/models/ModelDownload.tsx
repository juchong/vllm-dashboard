import { useState, useCallback } from 'react'
import axios from 'axios'

interface ModelDownloadProps {
  onSuccess: () => void
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

type DownloadState = 'idle' | 'starting' | 'started' | 'error'

const ModelDownload = ({ onSuccess, onClose }: ModelDownloadProps) => {
  const [modelName, setModelName] = useState('')
  const [revision, setRevision] = useState('')
  const [isValidating, setIsValidating] = useState(false)
  const [isLoadingRevisions, setIsLoadingRevisions] = useState(false)
  const [validation, setValidation] = useState<ModelValidation | null>(null)
  const [revisions, setRevisions] = useState<ModelRevisions | null>(null)
  const [downloadState, setDownloadState] = useState<DownloadState>('idle')
  const [downloadError, setDownloadError] = useState<string | null>(null)

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
      const response = await axios.get(`/api/models/validate/${name}`)
      setValidation(response.data.data)

      if (response.data.data.valid) {
        setIsLoadingRevisions(true)
        try {
          const revResponse = await axios.get(`/api/models/revisions/${name}`)
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

  const handleDownload = async () => {
    if (!modelName || !validation?.valid) return
    
    setDownloadState('starting')
    setDownloadError(null)
    
    try {
      await axios.post('/api/models/download', { 
        model_name: modelName.trim(), 
        revision: revision || undefined 
      })
      setDownloadState('started')
      // Close dialog after showing success message
      setTimeout(() => {
        onSuccess()
        onClose()
      }, 2000)
    } catch (err: any) {
      setDownloadState('error')
      const detail = err.response?.data?.detail || 'Failed to start download'
      setDownloadError(detail)
    }
  }

  const handleRetry = () => {
    setDownloadState('idle')
    setDownloadError(null)
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  const isStarting = downloadState === 'starting'
  const isStarted = downloadState === 'started'
  const isError = downloadState === 'error'

  return (
    <div className="modal-overlay">
      <div className="modal-container max-w-lg">
        <div className="modal-header">
          <h2 className="modal-title">Download Model from HuggingFace</h2>
          <button 
            onClick={onClose} 
            disabled={isStarting}
            className="modal-close disabled:opacity-50"
          >
            &times;
          </button>
        </div>
        
        <div className="modal-body space-y-4">
          {/* Status Banners */}
          {isStarting && (
            <div className="alert alert-info">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-600 border-t-transparent"></div>
                <p className="font-medium">Starting download...</p>
              </div>
            </div>
          )}

          {isStarted && (
            <div className="alert alert-success">
              <div className="flex items-center gap-3">
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <div>
                  <p className="font-medium">Download Started!</p>
                  <p className="text-sm opacity-90">
                    {modelName} is now downloading. Monitor progress on the Models page.
                  </p>
                </div>
              </div>
            </div>
          )}

          {isError && downloadError && (
            <div className="alert alert-error">
              <div className="flex items-start gap-3">
                <svg className="h-5 w-5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <div className="flex-1 min-w-0">
                  <p className="font-medium">Failed to Start Download</p>
                  <p className="text-sm break-words opacity-90">{downloadError}</p>
                </div>
              </div>
            </div>
          )}

          {/* Model Name Input */}
          <div>
            <label className="form-label">
              Model Name <span className="text-red-500">*</span>
            </label>
            <input 
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              onBlur={handleModelNameBlur}
              placeholder="organization/model-name"
              disabled={isStarting || isStarted}
              className={`form-input disabled:bg-gray-100 disabled:cursor-not-allowed ${
                validation 
                  ? validation.valid 
                    ? 'border-green-500 bg-green-50 focus:ring-green-500' 
                    : 'border-red-500 bg-red-50 focus:ring-red-500'
                  : ''
              }`}
            />
            <p className="form-hint">
              Format: org/model (e.g., Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8)
            </p>

            {/* Validation Status */}
            {isValidating && (
              <p className="text-sm text-blue-600 mt-2">Validating model...</p>
            )}
            {validation && !isValidating && downloadState === 'idle' && (
              <div className={`mt-2 p-2 rounded-md text-sm ${validation.valid ? 'bg-green-100' : 'bg-red-100'}`}>
                {validation.valid ? (
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <span className="text-green-800 font-medium">Model found</span>
                    <div className="flex gap-2 text-xs text-gray-600">
                      {validation.downloads !== undefined && (
                        <span className="badge badge-gray">{formatNumber(validation.downloads)} downloads</span>
                      )}
                      {validation.likes !== undefined && (
                        <span className="badge badge-gray">{formatNumber(validation.likes)} likes</span>
                      )}
                      {validation.pipeline_tag && (
                        <span className="badge badge-blue">{validation.pipeline_tag}</span>
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
            <label className="form-label">Revision</label>
            {isLoadingRevisions ? (
              <p className="text-sm text-gray-500">Loading revisions...</p>
            ) : revisions && revisions.branches.length > 0 ? (
              <select
                value={revision}
                onChange={(e) => setRevision(e.target.value)}
                disabled={isStarting || isStarted}
                className="form-select disabled:bg-gray-100 disabled:cursor-not-allowed"
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
                disabled={isStarting || isStarted}
                className="form-input disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            )}
            <p className="form-hint">
              Branch or tag to download (default: main)
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="modal-footer">
          <button 
            onClick={onClose}
            disabled={isStarting}
            className="dashboard-button-secondary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isStarted ? 'Close' : 'Cancel'}
          </button>
          
          {isError ? (
            <button 
              onClick={handleRetry}
              className="dashboard-button"
            >
              Try Again
            </button>
          ) : (
            <button 
              onClick={handleDownload}
              disabled={isStarting || !modelName.trim() || !validation?.valid || isStarted}
              className="dashboard-button disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isStarting ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span>
                  Starting...
                </span>
              ) : isStarted ? (
                'Started'
              ) : (
                'Download Model'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ModelDownload
