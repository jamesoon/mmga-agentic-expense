import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function Signup() {
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    employeeId: '',
    displayName: '',
  })
  const [validationError, setValidationError] = useState<string | null>(null)
  const { register, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    setValidationError(null)

    if (form.password !== form.confirmPassword) {
      setValidationError('Passwords do not match.')
      return
    }
    if (form.password.length < 8) {
      setValidationError('Password must be at least 8 characters.')
      return
    }

    try {
      await register({
        username: form.username,
        password: form.password,
        email: form.email,
        employeeId: form.employeeId,
        displayName: form.displayName,
      })
      navigate(`/verify?username=${encodeURIComponent(form.username)}`)
    } catch {
      // error is set in store
    }
  }

  const displayErr = validationError || error

  const inputStyle: React.CSSProperties = {
    background: 'var(--bg)',
    borderColor: 'var(--border)',
    color: 'var(--fg)',
  }

  const inputClass =
    'w-full rounded-lg px-3 py-2.5 text-sm border outline-none transition-colors'

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10" style={{ background: 'var(--bg)' }}>
      <div
        className="w-full max-w-sm rounded-xl border p-8 shadow-lg"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <h1 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
          Create account
        </h1>
        <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
          Expense Claims Portal
        </p>

        {displayErr && (
          <div
            className="mb-4 rounded-lg px-3 py-2 text-sm border"
            style={{ background: '#1f1215', borderColor: '#5c2025', color: 'var(--danger)' }}
          >
            {displayErr}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {[
            { name: 'username', label: 'Username', type: 'text', autoComplete: 'username' },
            { name: 'email', label: 'Email', type: 'email', autoComplete: 'email' },
            { name: 'displayName', label: 'Display name', type: 'text', autoComplete: 'name' },
            { name: 'employeeId', label: 'Employee ID', type: 'text', autoComplete: 'off' },
            { name: 'password', label: 'Password', type: 'password', autoComplete: 'new-password' },
            { name: 'confirmPassword', label: 'Confirm password', type: 'password', autoComplete: 'new-password' },
          ].map((field) => (
            <div key={field.name}>
              <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--muted)' }}>
                {field.label}
              </label>
              <input
                type={field.type}
                name={field.name}
                value={form[field.name as keyof typeof form]}
                onChange={handleChange}
                required
                autoComplete={field.autoComplete}
                className={inputClass}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = 'var(--accent)')}
                onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity disabled:opacity-60 mt-2"
            style={{ background: 'var(--accent)' }}
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <div className="mt-4 text-sm text-center" style={{ color: 'var(--muted)' }}>
          Already have an account?{' '}
          <Link to="/login" className="hover:underline" style={{ color: 'var(--accent)' }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  )
}
