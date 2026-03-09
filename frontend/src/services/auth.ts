/**
 * Authentication service
 * Handles authentication logic
 * 
 * @file auth.ts
 * @version 1.0.0
 */

import axios from 'axios'
import AuthAPI from './auth_api';

/**
 * Authentication state interface
 */
interface AuthState {
    isAuthenticated: boolean;
    user: AuthUser | null;
    loading: boolean;
    error: string | null;
    config: AuthConfig | null;
}

/**
 * Auth user interface
 */
interface AuthUser {
    id: number;
    username: string;
    role: 'viewer' | 'operator' | 'admin';
    is_active: boolean;
}

/**
 * Auth configuration interface
 */
interface AuthConfig {
    enabled: boolean;
    max_failed_attempts: number;
    lockout_minutes: number;
    token_expires_hours: number;
}

/**
 * Authentication service
 */
class AuthService {
    private state: AuthState;
    private listeners: Array<(state: AuthState) => void>;

    constructor() {
        this.state = {
            isAuthenticated: false,
            user: null,
            loading: false,
            error: null,
            config: null,
        };
        this.listeners = [];
    }

    /**
     * Get current state
     * @returns - Current state
     */
    getState(): AuthState {
        return this.state;
    }

    /**
     * Subscribe to state changes
     * @param listener - Listener function
     * @returns - Unsubscribe function
     */
    subscribe(listener: (state: AuthState) => void): () => void {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    /**
     * Notify listeners
     * @param newState - New state
     */
    private notifyListeners(): void {
        this.listeners.forEach(listener => listener(this.state));
    }

    /**
     * Update state
     * @param newState - New state
     */
    private setState(newState: Partial<AuthState>): void {
        this.state = { ...this.state, ...newState };
        this.notifyListeners();
    }

    /**
     * Login
     * @param username - Username
     * @param password - Password
     * @returns - True if login succeeded
     */
    async login(username: string, password: string): Promise<boolean> {
        try {
            this.setState({ loading: true, error: null });
            const loginResponse = await AuthAPI.login(username, password);
            // User from response; token is in httpOnly cookie only (never in JS)
            this.setState({
                isAuthenticated: true,
                user: loginResponse.user,
                loading: false,
                error: null,
            });
            
            return true;
        } catch (error: unknown) {
            let msg = 'Login failed';
            if (axios.isAxiosError(error)) {
                const d = error.response?.data?.detail;
                msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x?.msg ?? '').join(' ') : d ?? String(error.response?.status ?? error.message);
            }
            this.setState({ loading: false, error: msg || 'Login failed' });
            return false;
        }
    }

    /**
     * Logout - optimistic: clears state immediately, revokes token in background.
     * @returns - True (always, for instant UI response)
     */
    logout(): boolean {
        this.setState({ isAuthenticated: false, user: null, error: null });
        AuthAPI.logout().catch(() => { /* revoke in background; state already cleared */ });
        return true;
    }

    /**
     * Load user
     * @returns - True if user loaded
     */
    async loadUser(): Promise<boolean> {
        try {
            this.setState({ loading: true, error: null });
            const user = await AuthAPI.getCurrentUser();
            
            this.setState({
                isAuthenticated: true,
                user: user,
                loading: false,
            });
            
            return true;
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to load user';
            this.setState({ loading: false, isAuthenticated: false, user: null, error: msg || 'Failed to load user' });
            return false;
        }
    }

    /**
     * List users (admin only)
     * @returns - List of users
     */
    async listUsers(): Promise<AuthUser[]> {
        try {
            const users = await AuthAPI.listUsers();
            return users;
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to list users';
            throw new Error(msg || 'Failed to list users');
        }
    }

    /**
     * Create user (admin only)
     * @param username - Username
     * @param password - Password
     * @returns - Created user
     */
    async createUser(username: string, password: string, role: 'viewer' | 'operator' | 'admin'): Promise<AuthUser> {
        try {
            const user = await AuthAPI.createUser(username, password, role);
            return user;
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to create user';
            throw new Error(msg || 'Failed to create user');
        }
    }

    /**
     * Update user (admin only)
     * @param userId - User ID
     * @param role - Role
     * @param isActive - Active status
     * @returns - Updated user
     */
    async updateUser(userId: number, role: 'viewer' | 'operator' | 'admin', isActive: boolean): Promise<AuthUser> {
        try {
            const user = await AuthAPI.updateUser(userId, role, isActive);
            return user;
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to update user';
            throw new Error(msg || 'Failed to update user');
        }
    }

    /**
     * Delete user (admin only)
     * @param userId - User ID
     */
    async deleteUser(userId: number): Promise<void> {
        try {
            await AuthAPI.deleteUser(userId);
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to delete user';
            throw new Error(msg || 'Failed to delete user');
        }
    }

    /**
     * Get auth configuration
     * @returns - Auth configuration
     */
    async getAuthConfig(): Promise<AuthConfig> {
        try {
            const config = await AuthAPI.getAuthConfig();
            
            this.setState({
                config: config,
            });
            
            return config;
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to get auth configuration';
            throw new Error(msg || 'Failed to get auth configuration');
        }
    }

    /**
     * Update auth configuration (admin only)
     * @param config - Auth configuration
     */
    async updateAuthConfig(config: Partial<AuthConfig>): Promise<void> {
        try {
            await AuthAPI.updateAuthConfig(config);
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to update auth configuration';
            throw new Error(msg || 'Failed to update auth configuration');
        }
    }

    /**
     * Change current user's password
     * @param currentPassword - Current password
     * @param newPassword - New password
     */
    async changePassword(currentPassword: string, newPassword: string): Promise<void> {
        try {
            await AuthAPI.changePassword(currentPassword, newPassword);
        } catch (error: unknown) {
            const msg = axios.isAxiosError(error) ? error.response?.data?.detail : 'Failed to change password';
            throw new Error(msg || 'Failed to change password');
        }
    }
}

// Singleton instance
const authService = new AuthService();

export default authService;