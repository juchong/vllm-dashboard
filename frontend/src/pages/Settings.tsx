const Settings = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      
      <div className="dashboard-card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Dashboard Settings</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Auto-refresh interval</label>
            <select className="w-full border border-gray-300 rounded px-3 py-2">
              <option value="5">5 seconds</option>
              <option value="10">10 seconds</option>
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Log retention</label>
            <select className="w-full border border-gray-300 rounded px-3 py-2">
              <option value="100">100 lines</option>
              <option value="500">500 lines</option>
              <option value="1000">1000 lines</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Settings
