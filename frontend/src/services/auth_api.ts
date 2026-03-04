/**
 * Authentication API service
 * Handles authentication-related API calls
 * 
 * @file auth_api.ts
 * @version 1.0.0
 */

import api from './api';

/**
 * Login response interface.
 * Token is in httpOnly cookie only - never in response body.
 */
interface LoginResponse {
    user: CurrentUser;
    token_type: string;
    expires_in: number;
}

/**
 * Logout response interface
 */
interface LogoutResponse {
    message: string;
}

/**
 * Token refresh response interface.
 * Token is in httpOnly cookie only.
 */
interface TokenRefreshResponse {
    user: CurrentUser;
    token_type: string;
    expires_in: number;
}

/**
 * Current user interface
 */
interface CurrentUser {
    id: number;
    username: string;
    role: string;
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
 * User interface
 */
interface User {
    id: number;
    username: string;
    role: string;
    is_active: boolean;
}

/**
 * Auth API service
 */
const AuthAPI = {
    /**
     * Login
     * @param username - Username
     * @param password - Password
     * @returns - Login response
     */
    login: async (username: string, password: string): Promise<LoginResponse> => {
        const body = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`;
        const response = await api.post('/auth/login', body, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        });
        return response.data as LoginResponse;
    },
    
    /**
     * Logout
     * @returns - Logout response
     */
    logout: async (): Promise<LogoutResponse> => {
        const response = await api.post('/auth/logout');
        return response.data as LogoutResponse;
    },
    
    /**
     * Refresh token
     * @returns - Token refresh response
     */
    refreshToken: async (): Promise<TokenRefreshResponse> => {
        const response = await api.post('/auth/refresh');
        return response.data as TokenRefreshResponse;
    },
    
    /**
     * Get current user (uses httpOnly cookie).
     * @returns - Current user
     */
    getCurrentUser: async (): Promise<CurrentUser> => {
        const response = await api.get('/auth/me');
        return response.data as CurrentUser;
    },
    
    /**
     * List users
     * @returns - List of users
     */
    listUsers: async (): Promise<User[]> => {
        const response = await api.get('/auth/users');
        return response.data as User[];
    },
    
    /**
     * Create user
     * @param username - Username
     * @param password - Password
     * @returns - Created user
     */
    createUser: async (username: string, password: string): Promise<User> => {
        const response = await api.post('/auth/users', { username, password });
        return response.data as User;
    },
    
    /**
     * Update user
     * @param userId - User ID
     * @param role - Role
     * @param isActive - Active status
     * @returns - Updated user
     */
    updateUser: async (userId: number, role: string, isActive: boolean): Promise<User> => {
        const response = await api.put(`/auth/users/${userId}`, { role, is_active: isActive });
        return response.data as User;
    },
    
    /**
     * Delete user
     * @param userId - User ID
     * @returns - Success message
     */
    deleteUser: async (userId: number): Promise<{ message: string }> => {
        const response = await api.delete(`/auth/users/${userId}`);
        return response.data as { message: string };
    },
    
    /**
     * Get auth configuration
     * @returns - Auth configuration
     */
    getAuthConfig: async (): Promise<AuthConfig> => {
        const response = await api.get('/auth/config');
        return response.data as AuthConfig;
    },
    
    /**
     * Update auth configuration
     * @param config - Auth configuration
     * @returns - Success message
     */
    updateAuthConfig: async (config: Partial<AuthConfig>): Promise<{ message: string }> => {
        const response = await api.put('/auth/config', config);
        return response.data as { message: string };
    }
};

export default AuthAPI;