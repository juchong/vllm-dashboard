/**
 * Login component for vllm-dashboard
 * 
 * @file Login.tsx
 * @version 1.0.0
 */

import { useState, useEffect } from 'react'
import authService from '../services/auth'

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]{3,32}$/
const MIN_PASSWORD_LENGTH = 8
const MAX_PASSWORD_LENGTH = 72

const Login = () => {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState(authService.getState().error || '')
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        const fromStorage = sessionStorage.getItem('auth_error')
        if (fromStorage) {
            sessionStorage.removeItem('auth_error')
            setError(fromStorage)
            return
        }
        const err = authService.getState().error
        if (err) setError(err)
    }, [])

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError('')
        if (!username.trim()) {
            setError('Username is required')
            return
        }
        if (!USERNAME_PATTERN.test(username)) {
            setError('Username must be 3-32 characters, alphanumeric, underscore, or hyphen only')
            return
        }
        if (!password) {
            setError('Password is required')
            return
        }
        if (password.length < MIN_PASSWORD_LENGTH) {
            setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`)
            return
        }
        if (new TextEncoder().encode(password).length > MAX_PASSWORD_LENGTH) {
            setError(`Password must be at most ${MAX_PASSWORD_LENGTH} bytes`)
            return
        }
        setLoading(true)

        try {
            const ok = await authService.login(username, password)
            if (!ok) {
                setError(authService.getState().error || 'Login failed')
            }
            // On success, auth state update triggers App re-render and /login route redirects to /
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-md w-full space-y-8">
                <div>
                    <h2 className="text-center text-3xl font-extrabold text-gray-900">
                        Sign in to vllm-dashboard
                    </h2>
                </div>
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="space-y-4">
                        <div className="flex items-center border border-gray-300 rounded-md bg-white shadow-sm overflow-hidden">
                            <div className="pl-3 flex-shrink-0" aria-hidden="true">
                                <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 4zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                </svg>
                            </div>
                            <input
                                type="text"
                                className="flex-1 min-w-0 border-0 py-3 pl-3 pr-4 bg-transparent text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset sm:text-sm"
                                placeholder="Username"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                            />
                        </div>
                        <div className="flex items-center border border-gray-300 rounded-md bg-white shadow-sm overflow-hidden">
                            <div className="pl-3 flex-shrink-0" aria-hidden="true">
                                <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                </svg>
                            </div>
                            <input
                                type="password"
                                className="flex-1 min-w-0 border-0 py-3 pl-3 pr-4 bg-transparent text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset sm:text-sm"
                                placeholder="Password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    {error && <div className="text-red-500 text-sm text-center">{error}</div>}
                    <div>
                        <button
                            type="submit"
                            className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                            disabled={loading}
                        >
                            {loading ? 'Signing in...' : 'Sign in'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default Login