// Default timezone - will be overridden by server timezone
let serverTimezone = 'America/Los_Angeles'

export const setTimezone = (tz: string) => {
  if (tz) serverTimezone = tz
}

export const getTimezone = () => serverTimezone

export const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export const formatPercentage = (value: number): string => {
  return `${Math.round(value)}%`
}

export const formatTemperature = (celsius: number): string => {
  return `${celsius}°C`
}

export const formatPower = (watts: number): string => {
  return `${Math.round(watts / 1000)}W`
}

export const formatDate = (dateString: string): string => {
  try {
    return new Date(dateString).toLocaleString('en-US', {
      timeZone: serverTimezone,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return new Date(dateString).toLocaleString()
  }
}

export const formatDateTime = (dateString: string): string => {
  try {
    return new Date(dateString).toLocaleString('en-US', {
      timeZone: serverTimezone,
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return new Date(dateString).toLocaleString()
  }
}

export const formatTime = (dateString: string): string => {
  try {
    return new Date(dateString).toLocaleTimeString('en-US', {
      timeZone: serverTimezone,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return new Date(dateString).toLocaleTimeString()
  }
}

export const formatRelativeTime = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return formatDateTime(dateString)
}
