import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

interface EnvEditorProps {
  instanceId: string
  onClose: () => void
}

function parseEnvContent(raw: string): Array<{ key: string; value: string }> {
  const pairs: Array<{ key: string; value: string }> = []
  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eq = trimmed.indexOf('=')
    if (eq === -1) continue
    pairs.push({ key: trimmed.slice(0, eq), value: trimmed.slice(eq + 1) })
  }
  return pairs
}

const EnvEditor = ({ instanceId, onClose }: EnvEditorProps) => {
  const [vars, setVars] = useState<Array<{ key: string; value: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchActiveEnv = useCallback(async () => {
    try {
      const response = await api.get(`/vllm/${instanceId}/env/env.active`)
      const raw = response.data.data?.content || ''
      setVars(parseEnvContent(raw))
    } catch (err) {
      setError('Failed to fetch active environment')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [instanceId])

  useEffect(() => {
    fetchActiveEnv()
  }, [fetchActiveEnv])

  return (
    <div className="modal-overlay">
      <div className="modal-container max-w-2xl max-h-[80vh] flex flex-col">
        <div className="modal-header">
          <div className="flex items-center gap-3">
            <h2 className="modal-title">Active Environment Variables</h2>
            {!loading && !error && (
              <span className="badge badge-gray">{vars.length} variable{vars.length !== 1 ? 's' : ''}</span>
            )}
          </div>
          <button onClick={onClose} className="modal-close">&times;</button>
        </div>

        <div className="modal-body flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-dim">Loading...</div>
            </div>
          ) : error ? (
            <div className="alert alert-error text-sm">{error}</div>
          ) : vars.length === 0 ? (
            <div className="text-dim text-sm text-center py-8">
              No environment variables configured for the active model.
            </div>
          ) : (
            <div className="border border-default rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="surface-secondary border-b border-default">
                    <th className="text-left px-3 py-2 text-dim font-medium">Variable</th>
                    <th className="text-left px-3 py-2 text-dim font-medium">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {vars.map(({ key, value }) => (
                    <tr key={key} className="surface-hover">
                      <td className="px-3 py-2 font-mono text-xs text-heading whitespace-nowrap">{key}</td>
                      <td className="px-3 py-2 font-mono text-xs text-body break-all">{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <span className="text-xs text-dim mr-auto">
            Defined in the active model's configuration. Use Reload Config to apply changes.
          </span>
          <button onClick={onClose} className="dashboard-button-secondary btn-sm">
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default EnvEditor
