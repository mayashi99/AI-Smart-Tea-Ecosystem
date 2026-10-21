import { useEffect, useState } from 'react'
import GlobeCanvas from '../components/GlobeCanvas'
import Icon from '../components/Icon'
import { Link } from '../components/ui'
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
  { value: 'farmer_seller', label: 'Farmer / Seller', icon: 'leaf', description: 'Register tea batches and track export readiness.' },
  { value: 'viewer_buyer', label: 'Viewer / Buyer', icon: 'package', description: 'Explore market signals and verify tea passports.' },
  { value: 'export_manager', label: 'Export Manager', icon: 'globe', description: 'Plan exports with forecasts and readiness checks.', approver: 'Admin' },
  { value: 'quality_officer', label: 'Quality & Compliance', icon: 'clipboard', description: 'Review readiness and quality evidence.', approver: 'Admin' },
  { value: 'data_analyst', label: 'Data Analyst', icon: 'bars', description: 'Work with forecasts, models and reports.', approver: 'Admin' },
  { value: 'admin', label: 'Admin', icon: 'settings', description: 'Manage users, roles and platform settings.', approver: 'Super Admin' },
]

const highlights = [
  { icon: 'trend', title: 'Demand forecasting', text: '12-month ML export outlook by market' },
  { icon: 'clipboard', title: 'Export readiness', text: 'Explainable readiness index per batch' },
  { icon: 'shield', title: 'Digital tea passport', text: 'QR-verified, hash-linked traceability' },
]

const emailIsValid = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
const startGoogleAuth = ({ intent, email, role, displayName }) => {
  const query = new URLSearchParams({ intent, email: email.trim() })
  if (intent === 'signup') query.set('role', role)
  if (displayName) query.set('display_name', displayName.trim())
  window.location.assign(`/api/auth/google/start?${query}`)
}

function GoogleMark() {
  return (
    <svg className="google-mark" viewBox="0 0 48 48" width="20" height="20" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

function Alert({ children, tone = 'error' }) {
  return (
    <p className={`auth-alert is-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={tone === 'error' ? 'alert' : 'info'} size={18} />
      <span>{children}</span>
    </p>
  )
}

function EmailField({ email, setEmail, role, roleLoading, autoFocus = false }) {
  return (
    <label className="field auth-field">
      <span>Email address</span>
      <span className="auth-input">
        <Icon name="mail" size={18} />
        <input
          type="email"
          name="username"
          required
          maxLength={254}
          autoComplete="email"
          autoFocus={autoFocus}
          placeholder="you@example.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        {emailIsValid(email) && (roleLoading || role) && (
          <span className={`auth-role-hint ${role ? 'is-known' : ''}`} aria-live="polite">
            {roleLoading ? 'Checking…' : role}
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

function LoginForm() {
  const { query } = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [adminMode, setAdminMode] = useState(query.get('error') === 'super-admin-password')
  const [showPassword, setShowPassword] = useState(false)
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

  function submitGoogle(event) {
    event.preventDefault()
    startGoogleAuth({ intent: 'login', email })
  }

  function startOver() {
    setChallenge(null)
    setCode('')
    setAuthError('')
  }

  if (challenge) {
    return (
      <>
        <header className="auth-heading">
          <span className="auth-step"><Icon name="lock" size={14} />Step 2 of 2 · Two-factor check</span>
          <h1>Verify it&apos;s you</h1>
          <p>{challenge.setup_required ? 'Finish setting up Google Authenticator for this Super Admin account.' : 'Enter the current six-digit code from Google Authenticator.'}</p>
        </header>
        <form className="auth-form" onSubmit={submitCode}>
          {challenge.setup_required && (
            <div className="totp-setup">
              <img src={challenge.qr_code} alt="Google Authenticator setup QR code" />
              <div>
                <h2>Scan with Google Authenticator</h2>
                <p>Then enter the six-digit code the app shows.</p>
                <small>Can&apos;t scan? Enter this key manually: <strong>{challenge.manual_entry_key}</strong></small>
              </div>
            </div>
          )}
          <label className="field auth-field">
            <span>Authenticator code</span>
            <input
              className="auth-otp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              pattern="[0-9]{6}"
              minLength={6}
              maxLength={6}
              required
              placeholder="••••••"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
            />
          </label>
          {authError && <Alert>{authError}</Alert>}
          <button className="btn auth-submit" type="submit" disabled={busy || code.length !== 6}>
            {busy ? <><span className="auth-spinner" aria-hidden="true" />Verifying…</> : <>Verify and open dashboard<Icon name="arrowRight" size={18} /></>}
          </button>
          <button className="auth-link-button" type="button" onClick={startOver}>
            <Icon name="arrowLeft" size={15} />Use a different account
          </button>
        </form>
      </>
    )
  }

  return (
    <>
      <header className="auth-heading">
        <h1>Welcome back</h1>
        <p>{adminMode ? 'Super Admin sign-in uses your password and a Google Authenticator code.' : 'Sign in with the Google account registered to your workspace.'}</p>
      </header>
      <form className="auth-form" onSubmit={adminMode ? submitPassword : submitGoogle}>
        <EmailField email={email} setEmail={setEmail} role={roleHint.role} roleLoading={roleHint.loading} autoFocus />
        {adminMode ? (
          <>
            <label className="field auth-field">
              <span>Super Admin password</span>
              <span className="auth-input">
                <Icon name="lock" size={18} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  required
                  maxLength={128}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <button
                  type="button"
                  className="auth-input-action"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  <Icon name={showPassword ? 'eyeOff' : 'eye'} size={18} />
                </button>
              </span>
            </label>
            <label className="auth-check">
              <input
                type="checkbox"
                checked={saveInPasswordManager}
                onChange={(event) => setSaveInPasswordManager(event.target.checked)}
              />
              <span>Save this login in my browser password manager</span>
            </label>
            {(authError || error) && <Alert>{authError || error}</Alert>}
            <button className="btn auth-submit" type="submit" disabled={busy || !emailIsValid(email) || !password}>
              {busy ? <><span className="auth-spinner" aria-hidden="true" />Checking credentials…</> : <>Continue<Icon name="arrowRight" size={18} /></>}
            </button>
            <div className="auth-divider"><span>or</span></div>
            <button className="btn auth-alt" type="button" onClick={() => { setAdminMode(false); setAuthError('') }}>
              <GoogleMark />Use Google sign-in instead
            </button>
          </>
        ) : (
          <>
            {error && <Alert>{error}</Alert>}
            <button className="btn auth-google" type="submit" disabled={!emailIsValid(email)}>
              <GoogleMark />Continue with Google
            </button>
            <div className="auth-divider"><span>or</span></div>
            <button className="btn auth-alt" type="button" onClick={() => setAdminMode(true)}>
              <Icon name="key" size={18} />Sign in as Super Admin
            </button>
          </>
        )}
      </form>
      <p className="auth-switch">New to TeaExportAI? <Link to="/signup">Create an account</Link></p>
    </>
  )
}

function SignupForm() {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('farmer_seller')
  const roleHint = useRoleHint(email)
  const selected = signUpRoles.find((item) => item.value === role)
  const accountExists = emailIsValid(email) && Boolean(roleHint.role)

  return (
    <>
      <header className="auth-heading">
        <h1>Create your account</h1>
        <p>Tell us who you are and pick your role — then verify your email securely with Google.</p>
      </header>
      <form className="auth-form" onSubmit={(event) => { event.preventDefault(); startGoogleAuth({ intent: 'signup', email, role, displayName }) }}>
        <div className="auth-row">
          <label className="field auth-field">
            <span>Full name</span>
            <span className="auth-input">
              <Icon name="user" size={18} />
              <input required maxLength={100} autoComplete="name" autoFocus placeholder="Your name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </span>
          </label>
          <EmailField email={email} setEmail={setEmail} role={roleHint.role} roleLoading={roleHint.loading} />
        </div>
        {accountExists && (
          <Alert tone="info">This email already has a {roleHint.role} account. <Link to="/login">Sign in instead</Link>, or use a different Google account.</Alert>
        )}
        <fieldset className="role-picker">
          <legend>Choose your workspace role</legend>
          <div className="role-grid">
            {signUpRoles.map((item) => (
              <label key={item.value} className={`role-card ${role === item.value ? 'is-selected' : ''}`}>
                <input type="radio" name="role" value={item.value} checked={role === item.value} onChange={() => setRole(item.value)} />
                <span className="role-card-icon"><Icon name={item.icon} size={18} /></span>
                <span className="role-card-copy">
                  <strong>{item.label}</strong>
                  <small>{item.description}</small>
                </span>
                <em className={item.approver ? 'needs-approval' : ''}>{item.approver ? 'Approval' : 'Instant'}</em>
              </label>
            ))}
          </div>
        </fieldset>
        <p className="auth-note">
          <Icon name={selected?.approver ? 'clipboard' : 'check'} size={16} />
          {selected?.approver
            ? `${selected.label} requests stay pending until approved by ${selected.approver === 'Admin' ? 'an Admin or Super Admin' : 'the Super Admin'}.`
            : `${selected?.label} accounts are ready as soon as Google verifies your email.`}
        </p>
        <button className="btn auth-google" type="submit" disabled={!displayName.trim() || !emailIsValid(email) || accountExists}>
          <GoogleMark />Continue with Google
        </button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
    </>
  )
}

/** Split-screen sign-in / sign-up. One component for both so the globe keeps spinning between tabs. */
export function AuthPage({ mode = 'login' }) {
  const signup = mode === 'signup'
  return (
    <main className="auth-split">
      <aside className="auth-visual">
        <div className="landing-bokeh" aria-hidden="true"><i /><i /><i /><i /></div>
        <Link to="/" className="auth-visual-brand">
          <img src={teaExportLogo} alt="" />
          <span><strong>TeaExportAI</strong><small>AI Smart Tea Ecosystem</small></span>
        </Link>
        <GlobeCanvas className="auth-visual-globe" />
        <div className="auth-visual-copy">
          <p className="auth-visual-kicker">Ceylon tea · Global markets</p>
          <h2>{signup ? 'Join Sri Lanka’s connected tea export network.' : 'Sri Lankan tea, connected to the world.'}</h2>
          <ul>
            {highlights.map((item) => (
              <li key={item.title}>
                <span><Icon name={item.icon} size={18} /></span>
                <div><strong>{item.title}</strong><small>{item.text}</small></div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <section className="auth-main">
        <header className="auth-main-top">
          <Link to="/" className="auth-home-link"><Icon name="arrowLeft" size={16} />Home</Link>
          <Link to="/" className="auth-mobile-brand" aria-label="TeaExportAI home">
            <img src={teaExportLogo} alt="" /><strong>TeaExportAI</strong>
          </Link>
        </header>
        <div className={`auth-panel ${signup ? 'is-wide' : ''}`}>
          <nav className={`auth-tabs ${signup ? 'is-signup' : ''}`} aria-label="Account">
            <Link to="/login" aria-current={signup ? undefined : 'page'}>Sign in</Link>
            <Link to="/signup" aria-current={signup ? 'page' : undefined}>Create account</Link>
            <span className="auth-tabs-thumb" aria-hidden="true" />
          </nav>
          <div key={mode} className="auth-panel-body">
            {signup ? <SignupForm /> : <LoginForm />}
          </div>
        </div>
        <footer className="auth-main-foot"><Icon name="shield" size={14} />Secured with Google sign-in and role-based access</footer>
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
