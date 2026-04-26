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
    } catch { /* error in store */ }
  }

  const handleResend = async () => {
    setResent(false)
    await resendCode(username)
    setResent(true)
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm rounded-2xl p-8 shadow-sm" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2 mb-7">
          <div className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-xs" style={{ background: 'var(--accent)' }}>EC</div>
          <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>ExpenseClaims</span>
        </div>

        <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5 text-2xl" style={{ background: 'var(--accent-light)' }}>
          ✉
        </div>

        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--fg)' }}>Check your email</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          We sent a 6-digit code{username ? ` to the address for ${username}` : ''}. Enter it below to verify your account.
        </p>

        {error && (
          <div className="mb-4 rounded-lg px-3.5 py-2.5 text-sm flex gap-2" style={{ background: 'var(--danger-light)', color: 'var(--danger)', border: '1px solid #fecaca' }}>
            <span>⚠</span><span>{error}</span>
          </div>
        )}
        {resent && (
          <div className="mb-4 rounded-lg px-3.5 py-2.5 text-sm" style={{ background: 'var(--success-light)', color: 'var(--success)', border: '1px solid #bbf7d0' }}>
            Code resent successfully.
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Verification code</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              maxLength={6}
              placeholder="123456"
              className="w-full rounded-lg px-3.5 py-3 text-lg font-mono outline-none transition-all text-center tracking-[0.5em]"
              style={{ background: 'var(--surface-raised)', border: '1.5px solid var(--border)', color: 'var(--fg)' }}
              onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }}
              onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50"
            style={{ background: 'var(--accent)' }}
            onMouseEnter={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent-hover)' }}
            onMouseLeave={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent)' }}
          >
            {loading ? 'Verifying…' : 'Verify email →'}
          </button>
        </form>

        <div className="mt-4 flex flex-col gap-2 text-xs text-center" style={{ color: 'var(--muted)' }}>
          <button onClick={handleResend} className="hover:underline" style={{ color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer' }}>
            Didn't receive it? Resend code
          </button>
          <Link to="/login" className="hover:underline">Back to sign in</Link>
        </div>
      </div>
    </div>
  )
}
