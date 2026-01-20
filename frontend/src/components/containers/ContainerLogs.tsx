import { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'

interface ContainerLogsProps {
  containerName: string
  onClose: () => void
}

const ContainerLogs = ({ containerName, onClose }: ContainerLogsProps) => {
  const [logs, setLogs] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const intervalRef = useRef<number | null>(null)
  
  const fetchLogs = useCallback(async () => {
    try {
      const response = await axios.get(`/api/containers/logs`, {
        params: { container_name: containerName, tail: 200 }
      })
      setLogs(response.data.logs || 'No logs available')
      setError(null)
    } catch (err: any) {
      console.error('Failed to fetch logs:', err)
      setError(err.response?.data?.detail || 'Failed to fetch logs')
    } finally {
      setLoading(false)
    }
  }, [containerName])

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = window.setInterval(fetchLogs, 3000)
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [autoRefresh, fetchLogs])

  // Handle escape key to close
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl h-[80vh] flex flex-col">
        <div className="flex justify-between items-center p-4 border-b bg-gray-50 rounded-t-lg">
          <h2 className="text-lg font-semibold text-gray-900">
            Logs: <span className="text-blue-600">{containerName}</span>
          </h2>
          <div className="flex gap-2 items-center">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh
            </label>
            <button 
              onClick={fetchLogs}
              className="dashboard-button-secondary text-sm"
            >
              Refresh
            </button>
            <button 
              onClick={scrollToBottom}
              className="dashboard-button-secondary text-sm"
            >
              Scroll to Bottom
            </button>
            <button 
              onClick={onClose} 
              className="dashboard-button text-sm"
            >
              Close
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-4 bg-gray-900 text-gray-100 font-mono text-xs leading-relaxed">
          {loading ? (
            <div className="text-gray-400">Loading logs...</div>
          ) : error ? (
            <div className="text-red-400">Error: {error}</div>
          ) : (
            <>
              <pre className="whitespace-pre-wrap break-all">{logs}</pre>
              <div ref={logsEndRef} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ContainerLogs