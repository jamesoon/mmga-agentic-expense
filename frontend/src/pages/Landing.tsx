import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

type Tab = 'login' | 'register'

export default function Landing() {
  const [tab, setTab] = useState<Tab>('login')
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--bg)' }}>
      {/* Left hero panel */}
      <div
        className="hidden lg:flex lg:w-[46%] flex-col justify-between p-12"
        style={{ background: 'var(--sidebar-bg)' }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
            style={{ background: 'var(--accent)' }}
          >
            EC
          </div>
          <span className="text-white font-semibold text-sm tracking-wide">ExpenseClaims</span>
        </div>

        <div>
          <div
            className="inline-block text-xs font-semibold px-2.5 py-1 rounded-full mb-6 tracking-wider uppercase"
            style={{ background: '#1e293b', color: 'var(--accent)' }}
          >
            SUTD · MSTR-DAIE · 2026
          </div>
          <h1 className="text-4xl font-bold text-white leading-tight mb-4">
            Multimodal Agentic<br />Expense Claims
          </h1>
          <p className="text-base leading-relaxed" style={{ color: 'var(--sidebar-muted)' }}>
            AI-powered receipt processing that reduces claim time from 25 minutes to under 3.
            Upload receipts, let agents handle extraction, compliance, and routing.
          </p>

          <div className="mt-10 grid grid-cols-3 gap-6">
            {[
              { value: '<3 min', label: 'Per claim' },
              { value: '>95%', label: 'Accuracy' },
              { value: '4 agents', label: 'Pipeline' },
            ].map((stat) => (
              <div key={stat.label}>
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="text-xs mt-1" style={{ color: 'var(--sidebar-muted)' }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex -space-x-2">
            {['S', 'J', 'T', 'J'].map((initial, i) => (
              <div
                key={i}
                className="w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-semibold text-white"
                style={{ borderColor: 'var(--sidebar-bg)', background: ['#2563eb','#7c3aed','#059669','#d97706'][i] }}
              >
                {initial}
              </div>
            ))}
          </div>
          <span className="text-xs" style={{ color: 'var(--sidebar-muted)' }}>
            Used by the SUTD MSTR-DAIE team
          </span>
        </div>
      </div>

      {/* Right auth panel */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
              style={{ background: 'var(--accent)' }}
            >
              EC
            </div>
            <span className="font-semibold text-sm" style={{ color: 'var(--fg)' }}>ExpenseClaims</span>
          </div>

          <h2 className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
            {tab === 'login' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
            {tab === 'login' ? 'Sign in to your account to continue.' : 'Get started with expense claims today.'}
          </p>

          {/* Tabs */}
          <div
            className="flex rounded-lg p-1 mb-6"
            style={{ background: 'var(--bg)', border: '1px solid var(--border)' }}
          >
            {(['login', 'register'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="flex-1 py-2 text-sm font-medium rounded-md transition-all"
                style={
                  tab === t
                    ? { background: 'var(--surface)', color: 'var(--fg)', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }
                    : { color: 'var(--muted)' }
                }
              >
                {t === 'login' ? 'Sign in' : 'Register'}
              </button>
            ))}
          </div>

          {tab === 'login' ? (
            <LoginForm onSuccess={() => navigate('/chat')} />
          ) : (
            <RegisterForm onSuccess={(username) => navigate(`/verify?username=${encodeURIComponent(username)}`)} />
          )}

          {tab === 'login' && (
            <p className="text-xs text-center mt-5" style={{ color: 'var(--muted)' }}>
              Need an account?{' '}
              <button onClick={() => setTab('register')} className="font-medium hover:underline" style={{ color: 'var(--accent)' }}>
                Register here
              </button>
            </p>
          )}
          {tab === 'register' && (
            <p className="text-xs text-center mt-5" style={{ color: 'var(--muted)' }}>
              Already registered?{' '}
              <button onClick={() => setTab('login')} className="font-medium hover:underline" style={{ color: 'var(--accent)' }}>
                Sign in
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function InputField({
  label, type = 'text', name, value, onChange, autoComplete, placeholder,
}: {
  label: string; type?: string; name: string; value: string
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  autoComplete?: string; placeholder?: string
}) {
  return (
    <div>
      <label
        className="block text-xs font-semibold mb-1.5 uppercase tracking-wide"
        style={{ color: 'var(--muted)' }}
      >
        {label}
      </label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        required
        autoComplete={autoComplete}
        placeholder={placeholder}
        className="w-full rounded-lg px-3.5 py-2.5 text-sm outline-none transition-all"
        style={{
          background: 'var(--surface)',
          border: '1.5px solid var(--border)',
          color: 'var(--fg)',
        }}
        onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }}
        onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
      />
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="mb-4 rounded-lg px-3.5 py-2.5 text-sm flex items-start gap-2"
      style={{ background: 'var(--danger-light)', color: 'var(--danger)', border: '1px solid #fecaca' }}
    >
      <span className="mt-0.5">⚠</span>
      <span>{message}</span>
    </div>
  )
}

function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    try {
      await login(username, password)
      onSuccess()
    } catch { /* error in store */ }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <ErrorBanner message={error} />}
      <InputField label="Username" name="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" placeholder="your_username" />
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Password</label>
          <button type="button" onClick={() => navigate('/forgot-password')} className="text-xs hover:underline" style={{ color: 'var(--accent)' }}>
            Forgot password?
          </button>
        </div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          placeholder="••••••••"
          className="w-full rounded-lg px-3.5 py-2.5 text-sm outline-none transition-all"
          style={{ background: 'var(--surface)', border: '1.5px solid var(--border)', color: 'var(--fg)' }}
          onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; e.target.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.1)' }}
          onBlur={(e) => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none' }}
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50 mt-1"
        style={{ background: loading ? 'var(--muted)' : 'var(--accent)' }}
        onMouseEnter={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent-hover)' }}
        onMouseLeave={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent)' }}
      >
        {loading ? 'Signing in…' : 'Sign in →'}
      </button>
    </form>
  )
}

function RegisterForm({ onSuccess }: { onSuccess: (username: string) => void }) {
  const [form, setForm] = useState({ username: '', email: '', displayName: '', employeeId: '', password: '', confirmPassword: '' })
  const [validationError, setValidationError] = useState<string | null>(null)
  const { register, loading, error, clearError } = useAuthStore()

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
      onSuccess(form.username)
    } catch { /* error in store */ }
  }

  const displayErr = validationError || error

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {displayErr && <ErrorBanner message={displayErr} />}
      <div className="grid grid-cols-2 gap-3">
        <InputField label="Username" name="username" value={form.username} onChange={handleChange} autoComplete="username" placeholder="jsmith" />
        <InputField label="Employee ID" name="employeeId" value={form.employeeId} onChange={handleChange} autoComplete="off" placeholder="1010001" />
      </div>
      <InputField label="Display name" name="displayName" value={form.displayName} onChange={handleChange} autoComplete="name" placeholder="John Smith" />
      <InputField label="Email" type="email" name="email" value={form.email} onChange={handleChange} autoComplete="email" placeholder="john@sutd.edu.sg" />
      <div className="grid grid-cols-2 gap-3">
        <InputField label="Password" type="password" name="password" value={form.password} onChange={handleChange} autoComplete="new-password" placeholder="••••••••" />
        <InputField label="Confirm" type="password" name="confirmPassword" value={form.confirmPassword} onChange={handleChange} autoComplete="new-password" placeholder="••••••••" />
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50 mt-1"
        style={{ background: loading ? 'var(--muted)' : 'var(--accent)' }}
        onMouseEnter={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent-hover)' }}
        onMouseLeave={(e) => { if (!loading) (e.target as HTMLElement).style.background = 'var(--accent)' }}
      >
        {loading ? 'Creating account…' : 'Create account →'}
      </button>
    </form>
  )
}
