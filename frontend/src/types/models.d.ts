export interface ModelInfo {
  name: string
  path: string
  size: number
  size_human: string
  is_valid?: boolean
}

export interface ConfigPair {
  model_name: string
  config_path: string
}
