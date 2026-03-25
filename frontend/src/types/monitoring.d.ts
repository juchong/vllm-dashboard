export interface GPUMetric {
  index: number
  name: string
  temperature: number
  memory: {
    total: number
    used: number
    free: number
    usage_percent: number
  }
  power: {
    usage: number
    limit: number
    default_limit: number
    min_limit: number
    max_limit: number
  }
  utilization: {
    gpu: number
    memory: number
  }
}

export interface SystemMetric {
  cpu: {
    percent: number
    count: number
  }
  memory: {
    total: number
    available: number
    used: number
    percent: number
  }
  disk: {
    total: number
    used: number
    free: number
    percent: number
  }
  network: {
    io: any
  }
}
