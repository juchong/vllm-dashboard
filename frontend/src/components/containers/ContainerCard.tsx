import { ContainerStatus } from '../../types/docker'
import { formatRelativeTime } from '../../utils/formatters'

interface ContainerCardProps {
  container: ContainerStatus
  onStart: () => void
  onStop: () => void
  onRestart: () => void
  onViewLogs: () => void
}

const ContainerCard = ({ container, onStart, onStop, onRestart, onViewLogs }: ContainerCardProps) => {
  const getStatusClass = () => {
    switch (container.status.toLowerCase()) {
      case 'running':
        return 'status-running'
      case 'exited':
        return 'status-stopped'
      default:
        return 'status-restarting'
    }
  }

  return (
    <div className="dashboard-card">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{container.name}</h3>
          <p className="text-sm text-gray-500 mt-1">{container.image || container.id.substring(0, 12)}</p>
        </div>
        <span className={getStatusClass()}>{container.status}</span>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {container.status.toLowerCase() === 'running' ? (
          <>
            <button onClick={onStop} className="dashboard-button-secondary">Stop</button>
            <button onClick={onRestart} className="dashboard-button-secondary">Restart</button>
          </>
        ) : (
          <button onClick={onStart} className="dashboard-button">Start</button>
        )}
        <button onClick={onViewLogs} className="dashboard-button-secondary">View Logs</button>
      </div>

      <div className="text-sm text-gray-600">
        <p>Created: {formatRelativeTime(container.created)}</p>
      </div>
    </div>
  )
}

export default ContainerCard
