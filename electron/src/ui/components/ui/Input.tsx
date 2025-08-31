import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  loading?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, loading, className = '', ...props }, ref) => {
    const inputId = React.useId();
    const errorId = React.useId();

    return (
      <div className={`input-group ${className}`}>
        {label && (
          <label htmlFor={inputId} className="input-label text-sm font-medium mb-2 block">
            {label}
          </label>
        )}
        
        <div className="input-wrapper relative">
          {icon && (
            <div className="input-icon absolute left-3 top-1/2 transform -translate-y-1/2 text-muted pointer-events-none">
              {icon}
            </div>
          )}
          
          <input
            ref={ref}
            id={inputId}
            className={`input ${icon ? 'pl-10' : ''} ${error ? 'border-error' : ''} ${loading ? 'loading' : ''}`}
            aria-describedby={error ? errorId : undefined}
            {...props}
          />
          
          {loading && (
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
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
            </div>
          )}
        </div>
        
        {error && (
          <p id={errorId} className="text-sm text-error mt-2">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export { Input };