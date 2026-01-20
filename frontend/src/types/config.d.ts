export interface ConfigPair {
  model_name: string
  config_path: string
}

export interface ModelConfig {
  model: string
  dtype: string
  tensor_parallel_size?: number
  max_model_len?: number
  max_num_seqs?: number
  gpu_memory_utilization?: number
  enable_prefix_caching?: boolean
  enable_chunked_prefill?: boolean
  attention_backend?: string
  flashinfer_moe?: {
    enabled?: boolean
    backend?: string
  }
  [key: string]: any
}
