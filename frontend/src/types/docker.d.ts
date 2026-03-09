export interface ContainerStatus {
  name: string
  id: string
  status: string
  created: string
  image: string
  labels: Record<string, string>
}
