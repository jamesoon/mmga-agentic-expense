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
    } catch {
      // error is set in store
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-xl border p-8 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
          Sign in
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          Expense Claims Portal
        </p>

        {error && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-sm border"
            style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors"
              style={{
                background: 'var(--bg)',
                borderColor: 'var(--border)',
                color: 'var(--fg)',
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--accent)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors"
              style={{
                background: 'var(--bg)',
                borderColor: 'var(--border)',
                color: 'var(--fg)',
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--accent)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60"
            style={{ background: 'var(--accent)' }}
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className="mt-5 flex flex-col gap-2 text-sm text-center" style={{ color: 'var(--muted)' }}>
          <Link to="/forgot-password" className="hover:underline" style={{ color: 'var(--accent)' }}>
            Forgot password?
          </Link>
          <span>
            No account?{' '}
            <Link to="/signup" className="hover:underline" style={{ color: 'var(--accent)' }}>
              Sign up
            </Link>
          </span>
        </div>
      </div>
    </div>
  )
}
