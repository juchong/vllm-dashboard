type MessageCallback = (data: any) => void

class WebSocketService {
  private socket: WebSocket | null = null
  private messageCallbacks: Map<string, Set<MessageCallback>> = new Map()
  private reconnectTimeout: number | null = null
  private url: string

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.host}/ws/updates`
  }

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) return

    try {
      this.socket = new WebSocket(this.url)

      this.socket.onopen = () => {
        console.log('WebSocket connected')
      }

      this.socket.onclose = () => {
        console.log('WebSocket disconnected')
        // Reconnect after 3 seconds
        this.reconnectTimeout = window.setTimeout(() => this.connect(), 3000)
      }

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error)
      }

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const type = data.type || 'message'
          const callbacks = this.messageCallbacks.get(type)
          if (callbacks) {
            callbacks.forEach(cb => cb(data))
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
  }

  on(event: string, callback: MessageCallback): void {
    if (!this.messageCallbacks.has(event)) {
      this.messageCallbacks.set(event, new Set())
    }
    this.messageCallbacks.get(event)!.add(callback)
  }

  off(event: string, callback: MessageCallback): void {
    const callbacks = this.messageCallbacks.get(event)
    if (callbacks) {
      callbacks.delete(callback)
    }
  }

  send(data: any): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    }
  }
}

export default new WebSocketService()
