import { ModelInfo } from '../../types/models'
import ModelCard from './ModelCard'

interface ModelListProps {
  models: ModelInfo[]
  onDelete: (modelPath: string) => void
  onRename: (oldPath: string, newPath: string) => void
  onViewConfig: (modelName: string) => void
}

const ModelList = ({ 
  models, 
  onDelete, 
  onRename, 
  onViewConfig 
}: ModelListProps) => {
  if (models.length === 0) {
    return (
      <div className="dashboard-card text-center py-12 text-gray-500">
        <p className="text-lg mb-2">No models downloaded yet</p>
        <p className="text-sm">Use the "Download Model" button above to get started</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-700">
          {models.length} Model{models.length !== 1 ? 's' : ''} Downloaded
        </h2>
      </div>
      
      <div className="space-y-3">
        {models.map((model) => (
          <ModelCard 
            key={model.path}
            model={model}
            onDelete={() => onDelete(model.path)}
            onRename={(newName) => onRename(model.path, newName)}
            onViewConfig={() => onViewConfig(model.name)}
          />
        ))}
      </div>
    </div>
  )
}

export default ModelList
