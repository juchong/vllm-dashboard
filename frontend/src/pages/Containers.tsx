import { useState } from 'react'
import useDocker from '../components/hooks/useDocker'
import ContainerControls from '../components/containers/ContainerControls'
import ContainerLogs from '../components/containers/ContainerLogs'
import LoadingSpinner from '../components/common/LoadingSpinner'
import Alert from '../components/common/Alert'

const Containers = () => {
  const { containers, loading, error, fetchContainers, startContainer, stopContainer, restartContainer } = useDocker()
  const [showLogs, setShowLogs] = useState(false)
  const [selectedContainer, setSelectedContainer] = useState('')

  const handleViewLogs = (containerName: string) => {
    setSelectedContainer(containerName)
    setShowLogs(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-900">All vLLM Containers</h1>
        <button onClick={fetchContainers} className="dashboard-button">Refresh</button>
      </div>

      {loading && <LoadingSpinner message="Loading containers..." />}
      {error && <Alert type="error">{error}</Alert>}

      <ContainerControls 
        containers={containers}
        onStart={startContainer}
        onStop={stopContainer}
        onRestart={restartContainer}
        onViewLogs={handleViewLogs}
      />

      {showLogs && (
        <ContainerLogs 
          containerName={selectedContainer}
          onClose={() => setShowLogs(false)}
        />
      )}
    </div>
  )
}

export default Containers
