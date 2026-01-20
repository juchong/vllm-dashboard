import { useState } from 'react'
import { ModelInfo } from '../../types/models'

interface ModelCardProps {
  model: ModelInfo
  onDelete: () => void
  onRename: (newName: string) => void
  onViewConfig: () => void
}

const ModelCard = ({ model, onDelete, onRename, onViewConfig }: ModelCardProps) => {
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
    <div className="dashboard-card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        {/* Model Info */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="flex items-center gap-2 flex-wrap">
              <input 
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5 text-sm flex-1 min-w-[200px]"
                onKeyDown={(e) => e.key === 'Enter' && handleRename()}
              />
              <button onClick={handleRename} className="dashboard-button text-xs">Save</button>
              <button onClick={() => { setIsEditing(false); setNewName(model.name) }} className="dashboard-button-secondary text-xs">Cancel</button>
            </div>
          ) : (
            <>
              {orgName && (
                <span className="text-xs text-gray-500 font-medium">{orgName}/</span>
              )}
              <h3 className="text-base font-semibold text-gray-900 break-words" title={model.name}>
                {displayName}
              </h3>
              <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                <span className="font-medium text-gray-700">{model.size_human}</span>
                {model.is_valid && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">
                    Valid Model
                  </span>
                )}
              </div>
            </>
          )}
        </div>

        {/* Actions */}
        {!isEditing && (
          <div className="flex flex-col gap-1.5 shrink-0">
            <button 
              onClick={onViewConfig} 
              className="dashboard-button text-xs whitespace-nowrap"
            >
              Config
            </button>
            <button 
              onClick={() => setIsEditing(true)} 
              className="dashboard-button-secondary text-xs whitespace-nowrap"
            >
              Rename
            </button>
            <button 
              onClick={onDelete} 
              className="dashboard-button-secondary text-xs whitespace-nowrap text-red-600 hover:bg-red-50"
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
