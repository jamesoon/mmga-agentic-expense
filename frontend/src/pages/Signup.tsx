import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Signup() {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '', employeeId: '', displayName: '' })
  const [validationError, setValidationError] = useState<string | null>(null)
  const { register, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    setValidationError(null)
    if (form.password !== form.confirmPassword) { setValidationError('Passwords do not match.'); return }
    if (form.password.length < 8) { setValidationError('Password must be at least 8 characters.'); return }
    try {
      await register({ username: form.username, password: form.password, email: form.email, employeeId: form.employeeId, displayName: form.displayName })
      navigate(`/verify?username=${encodeURIComponent(form.username)}`)
    } catch { /* error in store */ }
  }

  const displayErr = validationError || error

  const inputClass = 'w-full rounded-lg px-3.5 py-2.5 text-sm outline-none transition-all'
  const inputStyle: React.CSSProperties = { background: 'var(--surface-raised)', border: '1.5px solid var(--border)', color: 'var(--fg)' }
  const onFocus = (e: React.FocusEvent<HTMLInputElement>) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }
  const onBlur = (e: React.FocusEvent<HTMLInputElement>) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10" style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-md rounded-2xl p-8 shadow-sm" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2 mb-7">
          <div className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-xs" style={{ background: 'var(--accent)' }}>EC</div>
          <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>ExpenseClaims</span>
        </div>

        <h1 className="text-xl font-bold mb-1" style={{ color: 'var(--fg)' }}>Create account</h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>Join the SUTD expense claims platform.</p>

        {displayErr && (
          <div className="mb-4 rounded-lg px-3.5 py-2.5 text-sm flex gap-2" style={{ background: 'var(--danger-light)', color: 'var(--danger)', border: '1px solid #fecaca' }}>
            <span>⚠</span><span>{displayErr}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {[
              { name: 'username', label: 'Username', type: 'text', autoComplete: 'username', placeholder: 'jsmith' },
              { name: 'employeeId', label: 'Employee ID', type: 'text', autoComplete: 'off', placeholder: '1010001' },
            ].map((f) => (
              <div key={f.name}>
                <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>{f.label}</label>
                <input type={f.type} name={f.name} value={form[f.name as keyof typeof form]} onChange={handleChange} required autoComplete={f.autoComplete} placeholder={f.placeholder} className={inputClass} style={inputStyle} onFocus={onFocus} onBlur={onBlur} />
              </div>
            ))}
          </div>

          {[
            { name: 'displayName', label: 'Display name', type: 'text', autoComplete: 'name', placeholder: 'John Smith' },
            { name: 'email', label: 'Email address', type: 'email', autoComplete: 'email', placeholder: 'john@sutd.edu.sg' },
          ].map((f) => (
            <div key={f.name}>
              <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>{f.label}</label>
              <input type={f.type} name={f.name} value={form[f.name as keyof typeof form]} onChange={handleChange} required autoComplete={f.autoComplete} placeholder={f.placeholder} className={inputClass} style={inputStyle} onFocus={onFocus} onBlur={onBlur} />
            </div>
          ))}

          <div className="grid grid-cols-2 gap-3">
            {[
              { name: 'password', label: 'Password', autoComplete: 'new-password' },
              { name: 'confirmPassword', label: 'Confirm', autoComplete: 'new-password' },
            ].map((f) => (
              <div key={f.name}>
                <label className="block text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>{f.label}</label>
                <input type="password" name={f.name} value={form[f.name as keyof typeof form]} onChange={handleChange} required autoComplete={f.autoComplete} placeholder="••••••••" className={inputClass} style={inputStyle} onFocus={onFocus} onBlur={onBlur} />
              </div>
            ))}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50 mt-1"
            style={{ background: 'var(--accent)' }}
            onMouseEnter={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent-hover)' }}
            onMouseLeave={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent)' }}
          >
            {loading ? 'Creating account…' : 'Create account →'}
          </button>
        </form>

        <p className="text-xs text-center mt-5" style={{ color: 'var(--muted)' }}>
          Already have an account?{' '}
          <Link to="/login" className="font-medium hover:underline" style={{ color: 'var(--accent)' }}>Sign in</Link>
        </p>
      </div>
    </div>
  )
}
