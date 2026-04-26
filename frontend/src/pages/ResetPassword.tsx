import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const username = searchParams.get('username') ?? ''
  const [code, setCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const { resetPass, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    setValidationError(null)

    if (newPassword !== confirmPassword) {
      setValidationError('Passwords do not match.')
      return
    }
    if (newPassword.length < 8) {
      setValidationError('Password must be at least 8 characters.')
      return
    }

    try {
      await resetPass(username, code, newPassword)
      navigate('/login')
    } catch {
      // error set in store
    }
  }

  const displayErr = validationError || error

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg)',
    borderColor: 'var(--border)',
    color: 'var(--fg)',
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-xl border p-8 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
          Reset password
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          {username ? `Resetting password for ${username}.` : 'Enter the code from your email and your new password.'}
        </p>

        {displayErr && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-sm border"
            style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
          >
            {displayErr}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
              Verification code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              placeholder="123456"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none tracking-widest text-center"
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = 'var(--accent)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
              New password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
              style={inputStyle}
              onFocus={(e) => (e.target.style.borderColor = 'var(--accent)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
              Confirm new password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none"
              style={inputStyle}
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
            {loading ? 'Resetting...' : 'Reset password'}
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
