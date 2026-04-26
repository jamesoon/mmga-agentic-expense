import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      await login(username, password)
      navigate('/chat')
    } catch { /* error in store */ }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-2xl p-8 shadow-sm"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2 mb-7">
          <div className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-xs" style={{ background: 'var(--accent)' }}>
            EC
          </div>
          <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>ExpenseClaims</span>
        </div>

        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--fg)' }}>Sign in</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>Welcome back — enter your credentials to continue.</p>

        {error && (
          <div className="mb-4 rounded-lg px-3.5 py-2.5 text-sm flex gap-2" style={{ background: 'var(--danger-light)', color: 'var(--danger)', border: '1px solid #fecaca' }}>
            <span>⚠</span><span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {[
            { label: 'Username', type: 'text', value: username, setter: setUsername, autoComplete: 'username', placeholder: 'your_username' },
            { label: 'Password', type: 'password', value: password, setter: setPassword, autoComplete: 'current-password', placeholder: '••••••••' },
          ].map((field) => (
            <div key={field.label}>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>
                  {field.label}
                </label>
                {field.label === 'Password' && (
                  <Link to="/forgot-password" className="text-xs hover:underline" style={{ color: 'var(--accent)' }}>
                    Forgot?
                  </Link>
                )}
              </div>
              <input
                type={field.type}
                value={field.value}
                onChange={(e) => field.setter(e.target.value)}
                required
                autoComplete={field.autoComplete}
                placeholder={field.placeholder}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm outline-none transition-all"
                style={{ background: 'var(--surface-raised)', border: '1.5px solid var(--border)', color: 'var(--fg)' }}
                onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }}
                onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50 mt-1"
            style={{ background: 'var(--accent)' }}
            onMouseEnter={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent-hover)' }}
            onMouseLeave={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent)' }}
          >
            {loading ? 'Signing in…' : 'Sign in →'}
          </button>
        </form>

        <p className="text-xs text-center mt-5" style={{ color: 'var(--muted)' }}>
          No account?{' '}
          <Link to="/signup" className="font-medium hover:underline" style={{ color: 'var(--accent)' }}>Register</Link>
        </p>
      </div>
    </div>
  )
}
