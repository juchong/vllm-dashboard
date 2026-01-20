import { useState, useEffect, useRef, useCallback } from 'react'

interface WebSocketData {
  type: string
  data?: any
  message?: string
}

const useWebSocket = (path: string) => {
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketData | null>(null)
  const [messages, setMessages] = useState<WebSocketData[]>([])
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)

  const connect = useCallback(() => {
    // Build WebSocket URL from current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}${path}`

    try {
      socketRef.current = new WebSocket(url)

      socketRef.current.onopen = () => {
        setIsConnected(true)
        console.log('WebSocket connected')
      }

      socketRef.current.onclose = () => {
        setIsConnected(false)
        console.log('WebSocket disconnected')
        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect()
        }, 3000)
      }

      socketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      socketRef.current.onmessage = (event) => {
        try {
          const data: WebSocketData = JSON.parse(event.data)
          setLastMessage(data)
          setMessages(prev => [...prev.slice(-99), data]) // Keep last 100 messages
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }, [path])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (socketRef.current) {
        socketRef.current.close()
      }
    }
  }, [connect])

  const sendMessage = useCallback((message: any) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message))
    }
  }, [])

  return {
    isConnected,
    lastMessage,
    messages,
    sendMessage
  }
}

export default useWebSocket
