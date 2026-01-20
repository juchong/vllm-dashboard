import { useState } from 'react'
import { ModelInfo } from '../../types/models'

interface ModelCardProps {
  model: ModelInfo
  isDownloading?: boolean
  onDelete: () => void
  onRename: (newName: string) => void
  onViewConfig: () => void
}

const ModelCard = ({ model, isDownloading, onDelete, onRename, onViewConfig }: ModelCardProps) => {
  const [isEditing, setIsEditing] = useState(false)
  const [newName, setNewName] = useState(model.name)

  const handleRename = () => {
    if (newName && newName !== model.name) {
      onRename(newName)
    }
    setIsEditing(false)
  }

  // Format model name for display (handle org/model format)
  const displayName = model.name.includes('/') 
    ? model.name.split('/').pop() 
    : model.name
  const orgName = model.name.includes('/') 
    ? model.name.split('/')[0] 
    : null

  return (
    <div className={`dashboard-card hover:shadow-md transition-shadow ${isDownloading ? 'border-blue-200 bg-blue-50' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        {/* Model Info */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="flex items-center gap-2 flex-wrap">
              <input 
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="form-input flex-1 min-w-[200px] text-sm"
                onKeyDown={(e) => e.key === 'Enter' && handleRename()}
              />
              <button onClick={handleRename} className="dashboard-button btn-xs">Save</button>
              <button onClick={() => { setIsEditing(false); setNewName(model.name) }} className="dashboard-button-secondary btn-xs">Cancel</button>
            </div>
          ) : (
            <>
              {orgName && (
                <span className="text-xs text-gray-500 font-medium">{orgName}/</span>
              )}
              <h3 className="text-base font-semibold text-gray-900 break-words" title={model.name}>
                {displayName}
              </h3>
              <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
                <span className="badge badge-gray">{model.size_human}</span>
                {isDownloading && (
                  <span className="badge badge-blue gap-1.5">
                    <span className="animate-spin rounded-full h-3 w-3 border-2 border-blue-600 border-t-transparent"></span>
                    Downloading...
                  </span>
                )}
              </div>
            </>
          )}
        </div>

        {/* Actions - only show if not downloading */}
        {!isEditing && !isDownloading && (
          <div className="flex flex-col gap-1.5 shrink-0">
            <button 
              onClick={onViewConfig} 
              className="dashboard-button btn-xs whitespace-nowrap"
            >
              Config
            </button>
            <button 
              onClick={() => setIsEditing(true)} 
              className="dashboard-button-secondary btn-xs whitespace-nowrap"
            >
              Rename
            </button>
            <button 
              onClick={onDelete} 
              className="dashboard-button-danger btn-xs whitespace-nowrap"
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {!isEditing && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500 truncate" title={model.path}>
          {model.path}
        </div>
      )}
    </div>
  )
}

export default ModelCard
