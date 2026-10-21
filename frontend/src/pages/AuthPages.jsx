import { useEffect, useState } from 'react'
import Icon from '../components/Icon'
import { useLocation } from '../lib/router'
import { endpoints, useApi } from '../services/api'
import teaExportLogo from '../assets/teaexport-logo.png'

const authErrors = {
  'account-disabled': 'This account is inactive. Contact an administrator.',
  'not-invited': 'This Google account has not been invited. Contact an administrator.',
  'email-mismatch': 'The Google account did not match the email address you entered.',
  'signup-failed': 'Could not create the account. Try again or contact support.',
  'pending-approval': 'Your role request is waiting for administrator approval. You will be able to sign in after it is approved.',
  'request-rejected': 'Your role request was not approved. Contact an administrator for assistance.',
  'super-admin-password': 'Super Admin must sign in with the password and Google Authenticator code.',
}

const signUpRoles = [
  ['admin', 'Admin (requires Super Admin approval)'],
  ['export_manager', 'Export Manager (requires Admin approval)'],
  ['quality_officer', 'Quality & Compliance Officer (requires Admin approval)'],
  ['data_analyst', 'Data Analyst (requires Admin approval)'],
  ['farmer_seller', 'Farmer / Seller'],
  ['viewer_buyer', 'Viewer / Buyer'],
]

const emailIsValid = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
const startGoogleAuth = ({ intent, email, role, displayName }) => {
  const query = new URLSearchParams({ intent, email: email.trim() })
  if (intent === 'signup') query.set('role', role)
  if (displayName) query.set('display_name', displayName.trim())
  window.location.assign(`/api/auth/google/start?${query}`)
}

function Brand({ subtitle }) {
  return (
    <div className="auth-brand">
      <img className="auth-logo" src={teaExportLogo} alt="" />
      <span><strong>TeaExportAI</strong><small>{subtitle}</small></span>
    </div>
  )
}

function EmailField({ email, setEmail, role, roleLoading, required = true }) {
  return (
    <label className="field">
      <span>Email address</span>
      <span className="auth-email-control">
        <input
          type="email"
          name="username"
          required={required}
          maxLength={254}
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        {email.includes('@') && (
          <span className={`auth-role-hint ${role ? 'is-known' : ''}`} aria-live="polite">
            {roleLoading ? 'Checking…' : role || 'Role-based access'}
          </span>
        )}
      </span>
    </label>
  )
}

function useRoleHint(email) {
  const [status, setStatus] = useState({ email: '', role: '', approvalStatus: '', loading: false })

  useEffect(() => {
    if (!emailIsValid(email)) {
      return undefined
    }
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setStatus({ email, role: '', approvalStatus: '', loading: true })
      try {
        const response = await fetch(`${endpoints.roleHint}?email=${encodeURIComponent(email.trim())}`, {
          credentials: 'include',
          signal: controller.signal,
        })
        if (!response.ok) throw new Error('Role lookup failed')
        const result = await response.json()
        const role = result.role || ''
        const approvalStatus = result.approval_status || ''
        setStatus({ email, role: approvalStatus === 'pending' ? `${role} · Pending approval` : role, approvalStatus, loading: false })
      } catch (error) {
        if (error.name !== 'AbortError') setStatus({ email, role: '', approvalStatus: '', loading: false })
      } finally {
        if (!controller.signal.aborted) setStatus((current) => ({ ...current, loading: false }))
      }
    }, 350)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [email])

  return {
    role: status.email === email ? status.role : '',
    loading: status.email === email && status.loading,
  }
}

export function LoginPage() {
  const { query } = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [saveInPasswordManager, setSaveInPasswordManager] = useState(false)
  const [challenge, setChallenge] = useState(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [authError, setAuthError] = useState('')
  const roleHint = useRoleHint(email)
  const error = authErrors[query.get('error')]

  async function submitPassword(event) {
    event.preventDefault()
    setAuthError('')
    setBusy(true)
    try {
      const response = await fetch('/api/auth/admin/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Admin sign-in failed')
      setChallenge(payload)
    } catch (requestError) {
      setAuthError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(event) {
    event.preventDefault()
    setAuthError('')
    setBusy(true)
    try {
      const response = await fetch('/api/auth/admin/login/verify', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge_id: challenge.challenge_id, code }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.detail || 'Authenticator verification failed')
      if (saveInPasswordManager) {
        const PasswordCredentialType = window.PasswordCredential
        if (PasswordCredentialType && navigator.credentials?.store) {
          try {
            await navigator.credentials.store(new PasswordCredentialType({
              id: email.trim(),
              password,
            }))
          } catch {
            window.alert('Sign-in succeeded, but your browser did not save the login. You can save it manually in your browser password manager.')
          }
        } else {
          window.alert('This browser does not support saving through the password manager option. Save this login manually in your browser password manager.')
        }
      }
      window.location.assign('/')
    } catch (requestError) {
      setAuthError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card panel">
        <Brand subtitle="Sri Lanka Tea Intelligence" />
        <p className="eyebrow">Welcome back</p>
        <h1>Sign in to your workspace</h1>
        <p>Super Admin signs in with a password and Google Authenticator. Other users can continue with their registered Google account.</p>
        <form className="form-grid auth-form" onSubmit={challenge ? submitCode : submitPassword}>
          <EmailField email={email} setEmail={setEmail} role={roleHint.role} roleLoading={roleHint.loading} />
          {!challenge && (
            <>
              <label className="field">
                <span>Super Admin password</span>
                <input
                  type="password"
                  name="password"
                  required
                  maxLength={128}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <label className="auth-remember-option">
                <input
                  type="checkbox"
                  checked={saveInPasswordManager}
                  onChange={(event) => setSaveInPasswordManager(event.target.checked)}
                />
                <span>Save this login in my browser password manager</span>
              </label>
              <button className="btn btn-primary auth-google-button" type="submit" disabled={busy || !emailIsValid(email) || !password}>
                {busy ? 'Checking credentials…' : 'Continue as Super Admin'}
              </button>
              <button
                className="btn btn-secondary auth-google-button"
                type="button"
                disabled={!emailIsValid(email)}
                onClick={() => startGoogleAuth({ intent: 'login', email })}
              >
                <span className="google-g" aria-hidden="true">G</span>Continue with Google
              </button>
            </>
          )}
          {challenge?.setup_required && (
            <div className="totp-setup">
              <h2>Set up Google Authenticator</h2>
              <p>Scan this QR code, then enter the six-digit code shown in the app to finish setup.</p>
              <img src={challenge.qr_code} alt="Google Authenticator setup QR code" />
              <small>Can't scan? Enter this key manually: <strong>{challenge.manual_entry_key}</strong></small>
            </div>
          )}
          {challenge && (
            <>
              {!challenge.setup_required && <p className="field-hint">Enter the current six-digit code from Google Authenticator.</p>}
              <label className="field">
                <span>Authenticator code</span>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  minLength={6}
                  maxLength={6}
                  required
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                />
              </label>
              <button className="btn btn-primary auth-google-button" type="submit" disabled={busy || code.length !== 6}>
                {busy ? 'Verifying…' : 'Verify and open dashboard'}
              </button>
            </>
          )}
          {(authError || error) && <p className="auth-error" role="alert">{authError || error}</p>}
        </form>
        {!challenge && <p className="auth-switch">New to TeaExportAI? <a href="/signup">Create an account</a></p>}
        {!challenge && <small>New Admin and staff registrations require approval before access is granted.</small>}
      </section>
    </main>
  )
}

export function SignupPage() {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('farmer_seller')
  const roleHint = useRoleHint(email)
  const selectedRole = signUpRoles.find(([value]) => value === role)?.[1] || ''

  return (
    <main className="auth-page">
      <section className="auth-card panel">
        <Brand subtitle="Join the tea export network" />
        <p className="eyebrow">Create your account</p>
        <h1>Sign up with Google</h1>
        <p>Set up your profile, then verify your email securely with Google.</p>
        <form className="form-grid auth-form" onSubmit={(event) => { event.preventDefault(); startGoogleAuth({ intent: 'signup', email, role, displayName }) }}>
          <label className="field">
            <span>Full name</span>
            <input required maxLength={100} autoComplete="name" placeholder="Your name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <EmailField email={email} setEmail={setEmail} role={roleHint.role || (email.includes('@') ? selectedRole : '')} roleLoading={roleHint.loading} />
          <label className="field">
            <span>Workspace role</span>
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {signUpRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          {emailIsValid(email) && roleHint.role && <p className="field-hint">This email already has a {roleHint.role} account. Sign in instead, or use a different Google account.</p>}
          <button className="btn btn-primary auth-google-button" type="submit" disabled={!displayName.trim() || !emailIsValid(email) || Boolean(roleHint.role)}>
            <span className="google-g" aria-hidden="true">G</span>Continue with Google
          </button>
        </form>
        <p className="auth-switch">Already have an account? <a href="/login">Sign in</a></p>
        <small>Admin, Export Manager, Quality &amp; Compliance Officer, and Data Analyst requests stay pending until approved by an Admin or Super Admin. Admin requests require Super Admin approval.</small>
      </section>
    </main>
  )
}

export function PublicPassportPage({ publicId }) {
  const { data, error, loading, reload } = useApi(endpoints.publicPassport(publicId))
  return (
    <main className="public-passport-page">
      <header className="public-passport-header">
        <img className="public-passport-logo" src={teaExportLogo} alt="" />
        <span><strong>TeaExportAI</strong><small>Public Tea Passport</small></span>
      </header>
      <section className="panel public-passport-card">
        <p className="eyebrow">Traceability passport</p>
        <h1>{data ? `Batch ${data.batch_id}` : 'Tea batch passport'}</h1>
        {error ? <div className="state-box is-error" role="alert">{error}<button className="btn btn-secondary btn-sm" onClick={reload}>Retry</button></div>
          : loading || !data ? <div className="state-box" role="status">Loading public passport…</div>
            : (
              <>
                <div className={`passport-verification ${data.ledger_verified ? 'is-verified' : 'is-invalid'}`} role="status">
                  <Icon name={data.ledger_verified ? 'shield' : 'alert'} size={19} />
                  <span>{data.ledger_verified ? 'Hash-linked record integrity verified' : 'Ledger integrity check failed'}</span>
                </div>
                <ol className="public-passport-timeline">
                  {data.events.map((event, index) => (
                    <li key={`${event.timestamp}-${index}`}>
                      <span className="activity-dot" />
                      <div><strong>{event.event_type}</strong><time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString()}</time></div>
                    </li>
                  ))}
                </ol>
                <p className="public-passport-disclaimer">The hash-chain check detects changes to recorded entries; it does not independently verify the truth of the original information. This is not a distributed blockchain.</p>
              </>
            )}
      </section>
    </main>
  )
}
