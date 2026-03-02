import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  title?: string
  className?: string
}

const Card = ({ children, title, className = '' }: CardProps) => {
  return (
    <div className={`dashboard-card ${className}`}>
      {title && (
        <h3 className="text-lg font-semibold text-heading mb-4">{title}</h3>
      )}
      {children}
    </div>
  )
}

export default Card
