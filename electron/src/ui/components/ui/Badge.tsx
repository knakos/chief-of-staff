import React from 'react';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'user' | 'agent' | 'system' | 'success' | 'warning' | 'error' | 'info';
  size?: 'small' | 'medium';
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', size = 'medium', className = '', children, ...props }, ref) => {
    const baseClasses = 'pill';
    const variantClasses = {
      default: '',
      user: 'user',
      agent: 'agent', 
      system: 'system',
      success: 'status-success',
      warning: 'status-warning',
      error: 'status-error',
      info: 'status-info'
    };
    const sizeClasses = {
      small: 'text-xs px-2 py-1',
      medium: ''
    };

    const classes = [
      baseClasses,
      variantClasses[variant],
      sizeClasses[size],
      className
    ].filter(Boolean).join(' ');

    return (
      <span ref={ref} className={classes} {...props}>
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';

export { Badge };