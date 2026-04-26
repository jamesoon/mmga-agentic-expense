import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function ForgotPassword() {
  const [username, setUsername] = useState('')
  const [sent, setSent] = useState(false)
  const { forgotPassword, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      await forgotPassword(username)
      setSent(true)
    } catch {
      // error set in store
    }
  }

  if (sent) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
        <div
          className="w-full max-w-sm rounded-xl border p-8 shadow-lg text-center"
          style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        >
          <h1 className="text-2xl font-bold mb-3" style={{ color: 'var(--fg)' }}>
            Check your email
          </h1>
          <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
            We sent a password reset code to the email associated with{' '}
            <span className="font-medium" style={{ color: 'var(--fg)' }}>{username}</span>.
          </p>
          <Link
            to={`/reset-password?username=${encodeURIComponent(username)}`}
            className="inline-block w-full py-2.5 rounded-lg text-sm font-semibold text-white text-center"
            style={{ background: 'var(--accent)' }}
          >
            Enter reset code
          </Link>
          <div className="mt-3">
            <button
              onClick={() => { setSent(false); navigate('/forgot-password') }}
              className="text-sm hover:underline"
              style={{ color: 'var(--muted)', background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Try a different username
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-xl border p-8 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
          Forgot password
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          Enter your username and we will send you a reset code.
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
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
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
            {loading ? 'Sending...' : 'Send reset code'}
          </button>
        </form>

        <div className="mt-4 text-sm text-center">
          <Link to="/login" className="hover:underline" style={{ color: 'var(--muted)' }}>
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
