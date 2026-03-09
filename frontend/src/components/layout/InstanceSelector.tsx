import { useInstanceContext } from '../../contexts/InstanceContext'

const InstanceSelector = () => {
  const { instances, selectedInstanceId, setSelectedInstanceId, loading } = useInstanceContext()

  if (loading || instances.length <= 1) return null

  return (
    <div className="px-4 py-2 border-b border-gray-700">
      <label className="block text-xs text-gray-400 mb-1">Instance</label>
      <select
        value={selectedInstanceId}
        onChange={(e) => setSelectedInstanceId(e.target.value)}
        className="w-full bg-gray-700 text-white text-sm rounded px-2 py-1.5 border border-gray-600 focus:border-blue-500 focus:outline-none"
      >
        {instances.map((inst) => (
          <option key={inst.id} value={inst.id}>
            {inst.display_name}
            {inst.vllm_status?.running ? ' ●' : ' ○'}
          </option>
        ))}
      </select>
    </div>
  )
}

export default InstanceSelector
