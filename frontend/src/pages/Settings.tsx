/**
 * Settings page for vllm-dashboard
 * 
 * @file Settings.tsx
 * @version 1.0.0
 */

import { useState, useEffect } from 'react'
import authService from '../services/auth'
import Alert from '../components/common/Alert'
import api from '../services/api'
import { useInstanceContext } from '../contexts/InstanceContext'

interface UserItem {
    id: number
    username: string
    role: 'viewer' | 'operator' | 'admin'
    is_active: boolean
    created_at?: string | null
}

const AUTH_BOUNDS = {
    max_failed_attempts: { min: 1, max: 20 },
    lockout_minutes: { min: 1, max: 1440 },
    token_expires_hours: { min: 1, max: 168 },
}

const Settings = () => {
    const currentUser = authService.getState().user
    const { instances, refreshInstances } = useInstanceContext()
    const [authConfig, setAuthConfig] = useState({
        enabled: true,
        max_failed_attempts: 5,
        lockout_minutes: 15,
        token_expires_hours: 8
    })
    const [users, setUsers] = useState<UserItem[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [successMsg, setSuccessMsg] = useState('')
    const [newUser, setNewUser] = useState({
        username: '',
        password: '',
        role: 'viewer' as 'viewer' | 'operator' | 'admin',
    })
    const [passwordForm, setPasswordForm] = useState({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
    })
    const [newInstance, setNewInstance] = useState({
        id: '',
        display_name: '',
        port: 8002,
        proxy_port: 4002,
        subdomain: '',
        gpu_device_ids: '' as string,
        api_key: '',
        expose_port: false,
    })
    const [editingLabels, setEditingLabels] = useState<{id: string, labels: Array<{key: string, value: string}>} | null>(null)
    const [editingInstance, setEditingInstance] = useState<{
        id: string
        display_name: string
        subdomain: string
        gpu_device_ids: string
        api_key: string
        expose_port: boolean
    } | null>(null)

    useEffect(() => {
        // Load auth configuration and users
        const loadSettings = async () => {
            try {
                const [config, users] = await Promise.all([
                    authService.getAuthConfig(),
                    authService.listUsers(),
                ])
                setAuthConfig(config)
                setUsers(users)
            } catch (err: unknown) {
                setError(err instanceof Error ? err.message : 'Failed to load settings')
            } finally {
                setLoading(false)
            }
        }
        loadSettings()
    }, [])

    const loadUsers = async () => {
        try {
            const list = await authService.listUsers()
            setUsers(list)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load users')
        }
    }

    const handleCreateUser = async () => {
        const un = newUser.username.trim()
        if (!un || un.length < 3 || un.length > 32 || !/^[a-zA-Z0-9_-]+$/.test(un)) {
            setError('Username must be 3-32 characters, alphanumeric, underscore, or hyphen only')
            return
        }
        if (!newUser.password || newUser.password.length < 8) {
            setError('Password must be at least 8 characters')
            return
        }
        if (new TextEncoder().encode(newUser.password).length > 72) {
            setError('Password must be at most 72 bytes')
            return
        }
        setError('')
        try {
            await authService.createUser(newUser.username, newUser.password, newUser.role)
            setNewUser({ username: '', password: '', role: 'viewer' })
            await loadUsers()
            setError('')
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to create user')
        }
    }

    const handleToggleActive = async (u: UserItem) => {
        if (currentUser && u.id === currentUser.id) {
            setError('You cannot deactivate your own account')
            return
        }
        setError('')
        try {
            await authService.updateUser(u.id, u.role, !u.is_active)
            await loadUsers()
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to update user')
        }
    }

    const handleDeleteUser = async (u: UserItem) => {
        if (currentUser && u.id === currentUser.id) {
            setError('You cannot delete your own account')
            return
        }
        if (!window.confirm(`Delete user "${u.username}"? This cannot be undone.`)) return
        setError('')
        try {
            await authService.deleteUser(u.id)
            await loadUsers()
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to delete user')
        }
    }

    const handleUpdateAuthConfig = async () => {
        const { max_failed_attempts, lockout_minutes, token_expires_hours } = authConfig
        const b = AUTH_BOUNDS
        if (max_failed_attempts < b.max_failed_attempts.min || max_failed_attempts > b.max_failed_attempts.max) {
            setError(`Max failed attempts must be between ${b.max_failed_attempts.min} and ${b.max_failed_attempts.max}`)
            return
        }
        if (lockout_minutes < b.lockout_minutes.min || lockout_minutes > b.lockout_minutes.max) {
            setError(`Lockout minutes must be between ${b.lockout_minutes.min} and ${b.lockout_minutes.max}`)
            return
        }
        if (token_expires_hours < b.token_expires_hours.min || token_expires_hours > b.token_expires_hours.max) {
            setError(`Token expires hours must be between ${b.token_expires_hours.min} and ${b.token_expires_hours.max}`)
            return
        }
        setError('')
        try {
            await authService.updateAuthConfig(authConfig)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to update config')
        }
    }

    const handleChangePassword = async () => {
        setError('')
        setSuccessMsg('')
        
        if (!passwordForm.currentPassword) {
            setError('Current password is required')
            return
        }
        if (!passwordForm.newPassword || passwordForm.newPassword.length < 8) {
            setError('New password must be at least 8 characters')
            return
        }
        if (new TextEncoder().encode(passwordForm.newPassword).length > 72) {
            setError('Password must be at most 72 bytes')
            return
        }
        if (passwordForm.newPassword !== passwordForm.confirmPassword) {
            setError('New passwords do not match')
            return
        }
        
        try {
            await authService.changePassword(passwordForm.currentPassword, passwordForm.newPassword)
            setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' })
            setSuccessMsg('Password changed successfully')
            setTimeout(() => setSuccessMsg(''), 5000)
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to change password')
        }
    }

    const [editingName, setEditingName] = useState<{id: string, name: string} | null>(null)

    const handleCreateInstance = async () => {
        setError('')
        if (!newInstance.id || !newInstance.display_name) {
            setError('Instance ID and display name are required')
            return
        }
        if (!/^[a-zA-Z0-9_-]+$/.test(newInstance.id)) {
            setError('Instance ID must be alphanumeric, hyphens, or underscores')
            return
        }
        try {
            const gpuIds = newInstance.gpu_device_ids.trim()
                ? newInstance.gpu_device_ids.split(',').map(s => s.trim()).filter(Boolean)
                : null
            await api.post('/instances', {
                id: newInstance.id,
                display_name: newInstance.display_name,
                port: newInstance.port,
                proxy_port: newInstance.proxy_port,
                subdomain: newInstance.subdomain || `vllm-${newInstance.id}`,
                gpu_device_ids: gpuIds,
                api_key: newInstance.api_key || null,
                expose_port: newInstance.expose_port,
            })
            setNewInstance({ id: '', display_name: '', port: 8002, proxy_port: 4002, subdomain: '', gpu_device_ids: '', api_key: '', expose_port: false })
            await refreshInstances()
            setSuccessMsg('Instance created')
            setTimeout(() => setSuccessMsg(''), 3000)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create instance')
        }
    }

    const handleDeleteInstance = async (instanceId: string) => {
        if (!window.confirm(`Delete instance "${instanceId}"? This will stop and remove its containers.`)) return
        setError('')
        try {
            await api.delete(`/instances/${instanceId}`)
            await refreshInstances()
            setSuccessMsg('Instance deleted')
            setTimeout(() => setSuccessMsg(''), 3000)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete instance')
        }
    }

    const handleRenameInstance = async (instanceId: string, displayName: string) => {
        setError('')
        try {
            await api.put(`/instances/${instanceId}`, { display_name: displayName })
            await refreshInstances()
            setEditingName(null)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to rename instance')
        }
    }

    const handleOpenLabels = (inst: any) => {
        const labelsObj = inst.labels || {}
        const pairs = Object.entries(labelsObj).map(([key, value]) => ({ key, value: String(value) }))
        if (pairs.length === 0) pairs.push({ key: '', value: '' })
        setEditingLabels({ id: inst.id, labels: pairs })
    }

    const handleSaveLabels = async () => {
        if (!editingLabels) return
        setError('')
        try {
            const labelsObj: Record<string, string> = {}
            for (const { key, value } of editingLabels.labels) {
                if (key.trim()) labelsObj[key.trim()] = value
            }
            await api.put(`/instances/${editingLabels.id}`, { labels: labelsObj })
            await refreshInstances()
            setEditingLabels(null)
            setSuccessMsg('Labels saved')
            setTimeout(() => setSuccessMsg(''), 3000)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save labels')
        }
    }

    const handleOpenEdit = (inst: any) => {
        setEditingInstance({
            id: inst.id,
            display_name: inst.display_name,
            subdomain: inst.subdomain || '',
            gpu_device_ids: inst.gpu_device_ids?.join(', ') || '',
            api_key: '',
            expose_port: inst.expose_port || false,
        })
    }

    const handleSaveEdit = async () => {
        if (!editingInstance) return
        setError('')
        try {
            const gpuIds = editingInstance.gpu_device_ids.trim()
                ? editingInstance.gpu_device_ids.split(',').map(s => s.trim()).filter(Boolean)
                : null
            const payload: Record<string, any> = {
                display_name: editingInstance.display_name,
                subdomain: editingInstance.subdomain,
                gpu_device_ids: gpuIds,
                expose_port: editingInstance.expose_port,
            }
            if (editingInstance.api_key) {
                payload.api_key = editingInstance.api_key
            }
            await api.put(`/instances/${editingInstance.id}`, payload)
            await refreshInstances()
            setEditingInstance(null)
            setSuccessMsg('Instance updated')
            setTimeout(() => setSuccessMsg(''), 3000)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to update instance')
        }
    }

    if (loading) {
        return (
            <div className="space-y-6">
                <h1 className="text-2xl font-bold text-heading">Settings</h1>
                <div className="dashboard-card">
                    <h2 className="text-lg font-semibold text-heading mb-4">Dashboard Settings</h2>
                    <p className="text-dim text-sm">Loading settings...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-heading">Settings</h1>
            
            {successMsg && <Alert type="success">{successMsg}</Alert>}
            {error && <Alert type="error">{error}</Alert>}
            
            <div className="space-y-6">
                {/* Change Password - available to all users */}
                <div className="dashboard-card">
                    <h2 className="text-lg font-semibold text-heading mb-4">Change Password</h2>
                    <p className="text-sm text-dim mb-4">Update your account password</p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                            <label className="form-label mb-2">Current Password</label>
                            <input
                                type="password"
                                className="form-input"
                                value={passwordForm.currentPassword}
                                onChange={(e) => setPasswordForm({...passwordForm, currentPassword: e.target.value})}
                            />
                        </div>
                        <div>
                            <label className="form-label mb-2">New Password</label>
                            <input
                                type="password"
                                className="form-input"
                                value={passwordForm.newPassword}
                                onChange={(e) => setPasswordForm({...passwordForm, newPassword: e.target.value})}
                            />
                        </div>
                        <div>
                            <label className="form-label mb-2">Confirm New Password</label>
                            <input
                                type="password"
                                className="form-input"
                                value={passwordForm.confirmPassword}
                                onChange={(e) => setPasswordForm({...passwordForm, confirmPassword: e.target.value})}
                            />
                        </div>
                    </div>
                    <button
                        className="dashboard-button mt-4"
                        onClick={handleChangePassword}
                    >
                        Change Password
                    </button>
                </div>

                {/* Instance Management - admin only */}
                {currentUser?.role === 'admin' && (
                <div className="dashboard-card">
                    <h2 className="text-lg font-semibold text-heading mb-4">vLLM Instances</h2>
                    <p className="text-sm text-dim mb-4">Create and manage vLLM inference instances</p>
                    
                    <div className="space-y-4">
                        <div className="border border-default rounded-lg overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="surface-secondary border-b border-default">
                                        <th className="text-left px-3 py-2 font-medium text-dim">ID</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">Name</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">vLLM Port</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">Subdomain</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">GPU IDs</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">API Key</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">Port Exposed</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">Status</th>
                                        <th className="text-left px-3 py-2 font-medium text-dim">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                                    {instances.map((inst) => (
                                        <tr key={inst.id} className="surface-hover">
                                            <td className="px-3 py-2 font-mono text-xs text-heading">{inst.id}</td>
                                            <td className="px-3 py-2 text-body">
                                                {editingName?.id === inst.id ? (
                                                    <form className="flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); handleRenameInstance(inst.id, editingName.name) }}>
                                                        <input type="text" className="form-input text-sm py-0.5 px-1 w-28"
                                                            value={editingName.name}
                                                            onChange={(e) => setEditingName({ id: inst.id, name: e.target.value })}
                                                            autoFocus
                                                            onBlur={() => setEditingName(null)}
                                                            onKeyDown={(e) => { if (e.key === 'Escape') setEditingName(null) }}
                                                        />
                                                    </form>
                                                ) : (
                                                    <span className="cursor-pointer hover:underline" onClick={() => setEditingName({ id: inst.id, name: inst.display_name })}>
                                                        {inst.display_name}
                                                    </span>
                                                )}
                                            </td>
                                            <td className="px-3 py-2 text-body font-mono text-xs">{inst.port}</td>
                                            <td className="px-3 py-2 text-body font-mono text-xs">{inst.subdomain}</td>
                                            <td className="px-3 py-2 text-body font-mono text-xs">{inst.gpu_device_ids?.join(', ') || 'all'}</td>
                                            <td className="px-3 py-2 text-body text-xs">
                                                <span className={inst.has_api_key ? 'text-green-600' : 'text-dim'}>{inst.has_api_key ? 'set' : 'none'}</span>
                                            </td>
                                            <td className="px-3 py-2 text-body text-xs">{inst.expose_port ? 'yes' : 'no'}</td>
                                            <td className="px-3 py-2">
                                                <span className={inst.vllm_status?.running ? 'status-running' : 'status-stopped'}>
                                                    {inst.vllm_status?.status || 'unknown'}
                                                </span>
                                            </td>
                                            <td className="px-3 py-2">
                                                <div className="flex gap-1">
                                                    {inst.managed_by === 'sdk' && (
                                                        <button onClick={() => handleOpenEdit(inst)}
                                                            className="dashboard-button-secondary btn-xs">
                                                            Edit
                                                        </button>
                                                    )}
                                                    <button onClick={() => handleOpenLabels(inst)}
                                                        className="dashboard-button-secondary btn-xs">
                                                        Labels
                                                    </button>
                                                    {inst.id !== 'default' && (
                                                        <button onClick={() => handleDeleteInstance(inst.id)}
                                                            className="dashboard-button-danger btn-xs">
                                                            Delete
                                                        </button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        <div className="border-t border-default pt-4">
                            <h3 className="text-body font-medium mb-3">Create New Instance</h3>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                <div>
                                    <label className="form-label mb-1">Instance ID</label>
                                    <input type="text" className="form-input" placeholder="beta"
                                        value={newInstance.id}
                                        onChange={(e) => setNewInstance({...newInstance, id: e.target.value})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">Display Name</label>
                                    <input type="text" className="form-input" placeholder="Secondary"
                                        value={newInstance.display_name}
                                        onChange={(e) => setNewInstance({...newInstance, display_name: e.target.value})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">vLLM Port</label>
                                    <input type="number" className="form-input"
                                        value={newInstance.port}
                                        onChange={(e) => setNewInstance({...newInstance, port: parseInt(e.target.value) || 8002})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">Proxy Port</label>
                                    <input type="number" className="form-input"
                                        value={newInstance.proxy_port}
                                        onChange={(e) => setNewInstance({...newInstance, proxy_port: parseInt(e.target.value) || 4002})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">Subdomain</label>
                                    <input type="text" className="form-input" placeholder="vllm-beta"
                                        value={newInstance.subdomain}
                                        onChange={(e) => setNewInstance({...newInstance, subdomain: e.target.value})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">GPU IDs (comma-sep, empty=all)</label>
                                    <input type="text" className="form-input" placeholder="0,1"
                                        value={newInstance.gpu_device_ids}
                                        onChange={(e) => setNewInstance({...newInstance, gpu_device_ids: e.target.value})} />
                                </div>
                                <div>
                                    <label className="form-label mb-1">API Key (optional)</label>
                                    <input type="password" className="form-input" placeholder="leave empty for global key"
                                        value={newInstance.api_key}
                                        onChange={(e) => setNewInstance({...newInstance, api_key: e.target.value})} />
                                </div>
                                <div className="flex items-end pb-1">
                                    <label className="flex items-center gap-2 text-sm text-body">
                                        <input type="checkbox" className="rounded"
                                            checked={newInstance.expose_port}
                                            onChange={(e) => setNewInstance({...newInstance, expose_port: e.target.checked})} />
                                        Expose port to host
                                    </label>
                                </div>
                            </div>
                            <button className="dashboard-button mt-3" onClick={handleCreateInstance}>
                                Create Instance
                            </button>
                        </div>
                    </div>
                </div>
                )}

                <div className="dashboard-card">
                    <h2 className="text-lg font-semibold text-heading mb-4">Authentication Settings</h2>
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="font-medium text-text">Authentication Enabled</h3>
                                <p className="text-sm text-dim">Require users to log in to access the dashboard</p>
                            </div>
                            <input
                                type="checkbox"
                                className="w-4 h-4 rounded"
                                checked={authConfig.enabled}
                                onChange={(e) => setAuthConfig({...authConfig, enabled: e.target.checked})}
                            />
                        </div>
                        {authConfig.enabled && (
                            <div className="space-y-4 mt-4 border-t pt-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="form-label mb-2">Max Failed Attempts</label>
                                        <input
                                            type="number"
                                            min={AUTH_BOUNDS.max_failed_attempts.min}
                                            max={AUTH_BOUNDS.max_failed_attempts.max}
                                            className="form-input"
                                            value={authConfig.max_failed_attempts}
                                            onChange={(e) => setAuthConfig({...authConfig, max_failed_attempts: parseInt(e.target.value) || 5})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label mb-2">Lockout Minutes</label>
                                        <input
                                            type="number"
                                            min={AUTH_BOUNDS.lockout_minutes.min}
                                            max={AUTH_BOUNDS.lockout_minutes.max}
                                            className="form-input"
                                            value={authConfig.lockout_minutes}
                                            onChange={(e) => setAuthConfig({...authConfig, lockout_minutes: parseInt(e.target.value) || 15})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label mb-2">Token Expires (Hours)</label>
                                        <input
                                            type="number"
                                            min={AUTH_BOUNDS.token_expires_hours.min}
                                            max={AUTH_BOUNDS.token_expires_hours.max}
                                            className="form-input"
                                            value={authConfig.token_expires_hours}
                                            onChange={(e) => setAuthConfig({...authConfig, token_expires_hours: parseInt(e.target.value) || 8})}
                                        />
                                    </div>
                                </div>
                                <button
                                    className="dashboard-button mt-4"
                                    onClick={handleUpdateAuthConfig}
                                >
                                    Save Auth Config
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div className="dashboard-card">
                    <h2 className="text-lg font-semibold text-heading mb-4">User Management</h2>
                    <p className="text-sm text-dim mb-4">Create and manage users with administrator permissions</p>
                    <div className="space-y-6">
                        <div>
                            <h3 className="text-body font-medium mb-3">Add new user</h3>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="form-label mb-2">Username</label>
                                    <input
                                        type="text"
                                        className="form-input"
                                        value={newUser.username}
                                        onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label className="form-label mb-2">Password</label>
                                    <input
                                        type="password"
                                        className="form-input"
                                        value={newUser.password}
                                        onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label className="form-label mb-2">Role</label>
                                    <select
                                        className="form-input"
                                        value={newUser.role}
                                        onChange={(e) => setNewUser({...newUser, role: e.target.value as 'viewer' | 'operator' | 'admin'})}
                                    >
                                        <option value="viewer">viewer</option>
                                        <option value="operator">operator</option>
                                        <option value="admin">admin</option>
                                    </select>
                                </div>
                            </div>
                            <button
                                className="dashboard-button mt-3"
                                onClick={handleCreateUser}
                            >
                                Create User
                            </button>
                        </div>
                        <div>
                            <h3 className="text-body font-medium mb-3">Registered users</h3>
                            {users.length === 0 ? (
                                <p className="text-sm text-dim">No users yet. Create one above.</p>
                            ) : (
                                <div className="border border-border-color rounded-md overflow-hidden">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="surface-secondary border-b border-border-color">
                                                <th className="text-left py-3 px-4 font-medium text-body">Username</th>
                                                <th className="text-left py-3 px-4 font-medium text-body">Role</th>
                                                <th className="text-left py-3 px-4 font-medium text-body">Status</th>
                                                <th className="text-left py-3 px-4 font-medium text-body">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {users.map((u) => (
                                                <tr key={u.id} className="border-b border-border-color last:border-0 surface-hover">
                                                    <td className="py-3 px-4 text-body">{u.username}</td>
                                                    <td className="py-3 px-4 text-body">{u.role}</td>
                                                    <td className="py-3 px-4">
                                                        <span className={u.is_active ? 'status-running' : 'status-stopped'}>
                                                            {u.is_active ? 'Active' : 'Inactive'}
                                                        </span>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <div className="flex gap-2">
                                                            {currentUser && u.id !== currentUser.id && (
                                                                <button
                                                                    onClick={() => handleToggleActive(u)}
                                                                    className="dashboard-button-ghost btn-xs"
                                                                >
                                                                    {u.is_active ? 'Deactivate' : 'Activate'}
                                                                </button>
                                                            )}
                                                            {currentUser && u.id !== currentUser.id && (
                                                                <button
                                                                    onClick={() => handleDeleteUser(u)}
                                                                    className="dashboard-button-danger btn-xs"
                                                                >
                                                                    Delete
                                                                </button>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            )                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {editingLabels && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="surface-primary rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
                        <div className="flex justify-between items-center p-4 border-b border-default">
                            <h2 className="text-lg font-semibold text-heading">Docker Labels: {editingLabels.id}</h2>
                            <button onClick={() => setEditingLabels(null)} className="text-dim hover:text-body text-xl">&times;</button>
                        </div>
                        <div className="p-4 flex-1 overflow-auto space-y-3">
                            <p className="text-xs text-dim">Docker labels applied to this instance's container. Use for Traefik routing, metadata, etc.</p>
                            <div className="space-y-2">
                                {editingLabels.labels.map((item, idx) => (
                                    <div key={idx} className="flex items-center gap-2">
                                        <input
                                            value={item.key}
                                            onChange={(e) => {
                                                const updated = [...editingLabels.labels]
                                                updated[idx] = { ...updated[idx], key: e.target.value }
                                                setEditingLabels({ ...editingLabels, labels: updated })
                                            }}
                                            className="form-input font-mono text-xs flex-1"
                                            placeholder="traefik.enable"
                                        />
                                        <span className="text-faint">=</span>
                                        <input
                                            value={item.value}
                                            onChange={(e) => {
                                                const updated = [...editingLabels.labels]
                                                updated[idx] = { ...updated[idx], value: e.target.value }
                                                setEditingLabels({ ...editingLabels, labels: updated })
                                            }}
                                            className="form-input font-mono text-xs flex-1"
                                            placeholder="true"
                                        />
                                        <button
                                            onClick={() => {
                                                const updated = editingLabels.labels.filter((_, i) => i !== idx)
                                                setEditingLabels({ ...editingLabels, labels: updated.length ? updated : [{ key: '', value: '' }] })
                                            }}
                                            className="text-red-500 hover:text-red-700 text-sm px-1"
                                        >&times;</button>
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={() => setEditingLabels({ ...editingLabels, labels: [...editingLabels.labels, { key: '', value: '' }] })}
                                className="text-sm text-blue-600 hover:text-blue-800"
                            >+ Add label</button>
                        </div>
                        <div className="flex justify-end gap-2 p-4 border-t border-default">
                            <button onClick={() => setEditingLabels(null)} className="dashboard-button-secondary btn-sm">Cancel</button>
                            <button onClick={handleSaveLabels} className="dashboard-button btn-sm">Save Labels</button>
                        </div>
                    </div>
                </div>
            )}

            {editingInstance && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="surface-primary rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
                        <div className="flex justify-between items-center p-4 border-b border-default">
                            <h2 className="text-lg font-semibold text-heading">Edit Instance: {editingInstance.id}</h2>
                            <button onClick={() => setEditingInstance(null)} className="text-dim hover:text-body text-xl">&times;</button>
                        </div>
                        <div className="p-4 flex-1 overflow-auto space-y-4">
                            <div>
                                <label className="form-label mb-1">Display Name</label>
                                <input type="text" className="form-input"
                                    value={editingInstance.display_name}
                                    onChange={(e) => setEditingInstance({ ...editingInstance, display_name: e.target.value })} />
                            </div>
                            <div>
                                <label className="form-label mb-1">Subdomain</label>
                                <input type="text" className="form-input"
                                    value={editingInstance.subdomain}
                                    onChange={(e) => setEditingInstance({ ...editingInstance, subdomain: e.target.value })} />
                            </div>
                            <div>
                                <label className="form-label mb-1">GPU IDs (comma-separated, empty = all)</label>
                                <input type="text" className="form-input" placeholder="0,1"
                                    value={editingInstance.gpu_device_ids}
                                    onChange={(e) => setEditingInstance({ ...editingInstance, gpu_device_ids: e.target.value })} />
                            </div>
                            <div>
                                <label className="form-label mb-1">API Key (leave blank to keep current)</label>
                                <input type="password" className="form-input" placeholder="unchanged"
                                    value={editingInstance.api_key}
                                    onChange={(e) => setEditingInstance({ ...editingInstance, api_key: e.target.value })} />
                            </div>
                            <div>
                                <label className="flex items-center gap-2 text-sm text-body">
                                    <input type="checkbox" className="rounded"
                                        checked={editingInstance.expose_port}
                                        onChange={(e) => setEditingInstance({ ...editingInstance, expose_port: e.target.checked })} />
                                    Expose port to host
                                </label>
                            </div>
                            <p className="text-xs text-dim">Changes to GPU IDs, API key, and expose port take effect on next container restart.</p>
                        </div>
                        <div className="flex justify-end gap-2 p-4 border-t border-default">
                            <button onClick={() => setEditingInstance(null)} className="dashboard-button-secondary btn-sm">Cancel</button>
                            <button onClick={handleSaveEdit} className="dashboard-button btn-sm">Save</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

export default Settings