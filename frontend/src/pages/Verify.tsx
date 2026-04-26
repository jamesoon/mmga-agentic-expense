import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Verify() {
  const [searchParams] = useSearchParams()
  const username = searchParams.get('username') ?? ''
  const [code, setCode] = useState('')
  const [resent, setResent] = useState(false)
  const { verify, resendCode, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      await verify(username, code)
      navigate('/login')
    } catch {
      // error set in store
    }
  }

  const handleResend = async () => {
    setResent(false)
    await resendCode(username)
    setResent(true)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-xl border p-8 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
          Verify email
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          Enter the 6-digit code sent to your email{username ? ` for ${username}` : ''}.
        </p>

        {error && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-sm border"
            style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
          >
            {error}
          </div>
        )}

        {resent && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-sm border"
            style={{ background: '#0d1f15', borderColor: '#1a5c35', color: 'var(--success)' }}
          >
            Verification code resent.
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
              maxLength={6}
              placeholder="123456"
              className="w-full rounded-lg px-3 py-2.5 text-sm border outline-none tracking-widest text-center"
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
            {loading ? 'Verifying...' : 'Verify'}
          </button>
        </form>

        <div className="mt-4 flex flex-col gap-2 text-sm text-center" style={{ color: 'var(--muted)' }}>
          <button
            onClick={handleResend}
            className="hover:underline"
            style={{ color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            Resend code
          </button>
          <Link to="/login" className="hover:underline" style={{ color: 'var(--muted)' }}>
            Back to sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
