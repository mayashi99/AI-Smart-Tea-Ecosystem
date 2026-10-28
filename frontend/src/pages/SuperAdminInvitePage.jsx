import { useEffect, useState } from 'react'
import Icon from '../components/Icon'
import { Link } from '../components/ui'
import { navigate } from '../lib/router'
import { endpoints, postJSON } from '../services/api'

export default function SuperAdminInvitePage() {
  const [inviteToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (inviteToken) window.history.replaceState({}, '', `${window.location.pathname}${window.location.search}`)
  }, [inviteToken])

  async function acceptInvite(event) {
    event.preventDefault()
    setError('')
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      const result = await postJSON(
        endpoints.acceptSuperAdminInvite,
        { invite_token: inviteToken, password },
        'Could not accept Super Admin invitation',
      )
      navigate(`/login?error=super-admin-password&email=${encodeURIComponent(result.email)}`)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-split">
      <section className="auth-main">
        <header className="auth-main-top">
          <Link to="/login" className="auth-home-link"><Icon name="arrowLeft" size={16} />Sign in</Link>
        </header>
        <div className="auth-panel">
          <div className="auth-panel-body">
            <div className="auth-heading">
              <span className="auth-step"><Icon name="shield" size={15} />Super Admin invitation</span>
              <h1>Set up Super Admin</h1>
              {inviteToken
                ? <p>Choose a password with at least 12 characters. You will set up Google Authenticator when you sign in.</p>
                : <p>This invitation link is missing or invalid. Ask the Super Admin for a new link.</p>}
            </div>
            {error && <p className="auth-alert is-error" role="alert">{error}</p>}
            {inviteToken ? (
              <form className="auth-form" onSubmit={acceptInvite}>
                <label className="field">
                  <span>Password</span>
                  <input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} />
                </label>
                <label className="field">
                  <span>Confirm password</span>
                  <input type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
                </label>
                <button className="btn auth-submit" disabled={busy}>{busy ? 'Setting up…' : 'Set password'}</button>
              </form>
            ) : <Link className="btn btn-primary" to="/login">Go to sign in</Link>}
          </div>
        </div>
        <footer className="auth-main-foot"><Icon name="shield" size={14} />Protected with password and Google Authenticator</footer>
      </section>
    </main>
  )
}
