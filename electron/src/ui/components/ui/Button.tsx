import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'small' | 'medium' | 'large';
  loading?: boolean;
  icon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ 
    variant = 'secondary', 
    size = 'medium', 
    loading = false,
    icon,
    children, 
    className = '', 
    disabled,
    ...props 
  }, ref) => {
    const baseClasses = 'btn';
    const variantClasses = {
      primary: 'primary',
      secondary: '',
      ghost: 'ghost',
      danger: 'danger'
    };
    const sizeClasses = {
      small: 'small',
      medium: '',
      large: 'large'
    };

    const classes = [
      baseClasses,
      variantClasses[variant],
      sizeClasses[size],
      loading && 'loading',
      className
    ].filter(Boolean).join(' ');

    return (
      <button
        ref={ref}
        className={classes}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <div className="loading-spinner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeDasharray="32"
                strokeDashoffset="32"
                style={{
                  animation: 'spin 1s linear infinite'
                }}
              />
            </svg>
          </div>
        )}
        {!loading && icon && <span className="btn-icon">{icon}</span>}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button };