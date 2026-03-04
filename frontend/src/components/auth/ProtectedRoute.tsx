import { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import authService from '../../services/auth'

interface ProtectedRouteProps {
  children: ReactNode
}

const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  if (!authService.getState().isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

export default ProtectedRoute
