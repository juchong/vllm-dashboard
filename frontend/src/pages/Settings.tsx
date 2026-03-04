/**
 * Settings page for vllm-dashboard
 * 
 * @file Settings.tsx
 * @version 1.0.0
 */

import { useState, useEffect } from 'react'
import authService from '../services/auth'
import Alert from '../components/common/Alert'

interface UserItem {
    id: number
    username: string
    role: string
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
    const [authConfig, setAuthConfig] = useState({
        enabled: true,
        max_failed_attempts: 5,
        lockout_minutes: 15,
        token_expires_hours: 8
    })
    const [users, setUsers] = useState<UserItem[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const [newUser, setNewUser] = useState({
        username: '',
        password: '',
        role: 'admin',
        is_active: true
    })

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
            await authService.createUser(newUser.username, newUser.password)
            setNewUser({ username: '', password: '', role: 'admin', is_active: true })
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
            
            <div className="space-y-6">
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
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                        {error && <Alert type="error">{error}</Alert>}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Settings