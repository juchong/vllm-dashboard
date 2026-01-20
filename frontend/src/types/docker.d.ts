export interface ContainerStatus {
  name: string
  id: string
  status: string
  created: string
  image: string
  labels: Record<string, string>
}

export interface ContainerMetric {
  cpu: any
  memory: any
  network: any
  blkio: any
}
