/**
 * Security test: YAML parsing must use safe schema (JSON_SCHEMA) to reject code execution.
 */
import { describe, it, expect } from 'vitest'
import yaml from 'js-yaml'

function validateYaml(yamlStr: string): { valid: boolean; parsed?: unknown } {
  try {
    const parsed = yaml.load(yamlStr, { schema: yaml.JSON_SCHEMA })
    return { valid: true, parsed }
  } catch {
    return { valid: false }
  }
}

describe('validateYaml security', () => {
  it('accepts valid vLLM config', () => {
    const config = `
model: Qwen/Qwen3-Coder-30B
dtype: bfloat16
tensor_parallel_size: 2
max_model_len: 8192
gpu_memory_utilization: 0.9
`
    const result = validateYaml(config)
    expect(result.valid).toBe(true)
    expect((result.parsed as Record<string, unknown>).model).toBe('Qwen/Qwen3-Coder-30B')
  })

  it('rejects !!js/function (code execution)', () => {
    const malicious = 'evil: !!js/function "function(){return 1}"'
    const result = validateYaml(malicious)
    expect(result.valid).toBe(false)
  })

  it('rejects !!js/regexp', () => {
    const malicious = 'pattern: !!js/regexp /test/g'
    const result = validateYaml(malicious)
    expect(result.valid).toBe(false)
  })
})
