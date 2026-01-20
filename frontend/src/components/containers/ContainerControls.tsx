import { ContainerStatus } from '../../types/docker'
import ContainerCard from './ContainerCard'

interface ContainerControlsProps {
  containers: ContainerStatus[]
  onStart: (containerName: string) => void
  onStop: (containerName: string) => void
  onRestart: (containerName: string) => void
  onViewLogs: (containerName: string) => void
}

const ContainerControls = ({ 
  containers, 
  onStart, 
  onStop, 
  onRestart, 
  onViewLogs 
}: ContainerControlsProps) => {
  if (containers.length === 0) {
    return (
      <div className="dashboard-card text-center text-gray-500">
        No vLLM containers found
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {containers.map((container) => (
        <ContainerCard 
          key={container.id}
          container={container}
          onStart={() => onStart(container.name)}
          onStop={() => onStop(container.name)}
          onRestart={() => onRestart(container.name)}
          onViewLogs={() => onViewLogs(container.name)}
        />
      ))}
    </div>
  )
}

export default ContainerControls
