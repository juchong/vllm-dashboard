import { useState, useCallback, useEffect } from 'react'
import api from '../../services/api'
import { ContainerStatus } from '../../types/docker'

const useDocker = () => {
  const [containers, setContainers] = useState<ContainerStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchContainers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get('/containers/status')
      // Transform object response to array with name property
      const data = response.data.data
      const containerArray: ContainerStatus[] = Object.entries(data).map(
        ([name, container]: [string, any]) => ({
          name,
          ...container
        })
      )
      setContainers(containerArray)
    } catch (err) {
      setError('Failed to fetch containers')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch containers on mount
  useEffect(() => {
    fetchContainers()
  }, [fetchContainers])

  const startContainer = async (containerName: string) => {
    setLoading(true)
    try {
      await api.post('/containers/start', { container_name: containerName })
      await fetchContainers()
    } catch (err) {
      setError('Failed to start container')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const stopContainer = async (containerName: string) => {
    setLoading(true)
    try {
      await api.post('/containers/stop', { container_name: containerName })
      await fetchContainers()
    } catch (err) {
      setError('Failed to stop container')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const restartContainer = async (containerName: string) => {
    setLoading(true)
    try {
      await api.post('/containers/restart', { container_name: containerName })
      await fetchContainers()
    } catch (err) {
      setError('Failed to restart container')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return {
    containers,
    loading,
    error,
    fetchContainers,
    startContainer,
    stopContainer,
    restartContainer
  }
}

export default useDocker
