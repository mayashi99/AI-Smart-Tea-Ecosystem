import { useMemo, useState } from 'react'
import { Card, ErrorState, LoadingState, PageHeader } from '../components/ui'
import { useAuth } from '../lib/auth-context'
import { endpoints, patchJSON, postJSON, useApi } from '../services/api'

const roles = [
  ['export_manager', 'Export Manager'],
  ['quality_officer', 'Quality & Compliance Officer'],
  ['data_analyst', 'Data Analyst'],
  ['farmer_seller', 'Farmer / Seller'],
  ['viewer_buyer', 'Viewer / Buyer'],
  ['admin', 'Admin'],
]

export default function UserManagementPage() {
  const { user: currentUser } = useAuth()
  const users = useApi(endpoints.users)
  const userRequests = useApi(endpoints.userRequests)
  const auditLog = useApi(endpoints.auditLog)
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('export_manager')
  const [superAdminEmail, setSuperAdminEmail] = useState('')
  const [superAdminName, setSuperAdminName] = useState('')
  const [superAdminInviteLink, setSuperAdminInviteLink] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [draftRoles, setDraftRoles] = useState({})
  const userNames = useMemo(() => new Map((users.data?.users || []).map((user) => [user.id, user.display_name])), [users.data])

  async function create(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await postJSON(endpoints.users, { email, display_name: displayName, role }, 'Could not create account')
      setEmail('')
      setDisplayName('')
      setMessage('Account created. The user can sign in with this Google email.')
      users.reload()
      auditLog.reload()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function createSuperAdminInvite(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const invitation = await postJSON(
        endpoints.superAdminInvites,
        { email: superAdminEmail, display_name: superAdminName },
        'Could not create Super Admin invitation',
      )
      const inviteUrl = new URL('/super-admin-invite', window.location.origin)
      inviteUrl.hash = `token=${invitation.invite_token}`
      setSuperAdminInviteLink(inviteUrl.toString())
      setSuperAdminEmail('')
      setSuperAdminName('')
      setMessage(`Invitation for ${invitation.email} created. It expires in 24 hours.`)
      auditLog.reload()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function update(user, changes) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await patchJSON(`${endpoints.users}/${user.id}`, changes, 'Could not update account')
      setMessage('Account updated.')
      users.reload()
      userRequests.reload()
      auditLog.reload()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  async function reviewRequest(request, status) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      await patchJSON(endpoints.userApproval(request.id), { status }, 'Could not review access request')
      setMessage(`${request.display_name}'s ${request.role.replaceAll('_', ' ')} request ${status}.`)
      users.reload()
      userRequests.reload()
      auditLog.reload()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow={currentUser?.is_super_admin ? 'Super Admin · Access control' : 'Admin · Access control'} title="User Management" description="Review role requests, manage accounts, and inspect recent audit activity." />
      {(error || users.error || userRequests.error || auditLog.error) && <ErrorState message={error || users.error || userRequests.error || auditLog.error} onRetry={() => { users.reload(); userRequests.reload(); auditLog.reload() }} />}
      {message && <p className="auth-success" role="status">{message}</p>}

      <Card icon="bell" title={`Role requests${userRequests.data?.requests?.length ? ` · ${userRequests.data.requests.length} awaiting review` : ''}`} description="Requested roles stay locked until an authorized administrator approves them. Admin requests can only be approved by the Super Admin.">
        {!userRequests.data && userRequests.loading ? <LoadingState compact label="Loading access requests…" /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Applicant</th><th>Requested role</th><th>Requested</th><th>Decision</th></tr></thead>
              <tbody>{(userRequests.data?.requests || []).map((request) => {
                const canReview = request.role !== 'admin' || currentUser?.is_super_admin
                return (
                  <tr key={request.id}>
                    <td><strong>{request.display_name}</strong><br /><small>{request.email}</small></td>
                    <td>{roles.find(([value]) => value === request.role)?.[1] || request.role}</td>
                    <td>{new Date(request.created_at).toLocaleDateString()}</td>
                    <td className="table-actions">
                      {canReview ? (
                        <>
                          <button className="btn btn-primary btn-sm" type="button" disabled={busy} onClick={() => reviewRequest(request, 'approved')}>Approve</button>
                          <button className="btn btn-ghost btn-sm" type="button" disabled={busy} onClick={() => reviewRequest(request, 'rejected')}>Reject</button>
                        </>
                      ) : <small>Super Admin review required</small>}
                    </td>
                  </tr>
                )
              })}{!(userRequests.data?.requests || []).length && <tr><td colSpan="4">No pending role requests.</td></tr>}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card icon="user" title="Add account" description="New accounts can authenticate only with the invited Google email address.">
        <form className="form-grid user-create-form" onSubmit={create}>
          <label className="field"><span>Name</span><input required maxLength={100} value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
          <label className="field"><span>Google account email</span><input type="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="field"><span>Role</span><select value={role} onChange={(event) => setRole(event.target.value)}>{roles.filter(([value]) => value !== 'admin').map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Create account'}</button>
        </form>
      </Card>

      {currentUser?.is_super_admin && (
        <Card icon="shield" title="Invite Super Admin" description="Create a one-time setup link for a new Super Admin. The invitee chooses their password and enrolls Google Authenticator on first sign-in. Creating another link for the same email invalidates the previous one.">
          <form className="form-grid user-create-form" onSubmit={createSuperAdminInvite}>
            <label className="field"><span>Name</span><input required maxLength={100} value={superAdminName} onChange={(event) => setSuperAdminName(event.target.value)} /></label>
            <label className="field"><span>Email address</span><input type="email" required maxLength={254} value={superAdminEmail} onChange={(event) => setSuperAdminEmail(event.target.value)} /></label>
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating link…' : 'Create invite link'}</button>
          </form>
          {superAdminInviteLink && (
            <label className="field auth-invite-link">
              <span>One-time link — share through a trusted channel</span>
              <input readOnly value={superAdminInviteLink} onFocus={(event) => event.target.select()} aria-label="One-time Super Admin invitation link" />
            </label>
          )}
        </Card>
      )}

      <Card icon="user" title="Accounts" description="Deactivated users are immediately signed out and cannot use protected APIs.">
        {!users.data && users.loading ? <LoadingState compact label="Loading accounts…" /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Created</th><th>Action</th></tr></thead>
              <tbody>{(users.data?.users || []).map((user) => (
                <tr key={user.id}>
                  <td><strong>{user.display_name}</strong><br /><small>{user.email}</small></td>
                  <td>{user.is_super_admin ? 'Super Admin' : user.role === 'admin' ? 'Admin' : <select aria-label={`Role for ${user.email}`} value={draftRoles[user.id] ?? user.role} onChange={(event) => setDraftRoles({ ...draftRoles, [user.id]: event.target.value })}>{roles.filter(([value]) => value !== 'admin').map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>}</td>
                  <td>{user.active ? 'Active' : 'Deactivated'}</td>
                  <td>{new Date(user.created_at).toLocaleDateString()}</td>
                  <td className="table-actions">
                    {user.is_super_admin ? <small>Protected account</small> : (
                      <>
                        {user.role !== 'admin' && <button className="btn btn-secondary btn-sm" type="button" disabled={busy || (draftRoles[user.id] ?? user.role) === user.role} onClick={() => update(user, { role: draftRoles[user.id] })}>Save role</button>}
                        <button className="btn btn-ghost btn-sm" type="button" disabled={busy || (user.role === 'admin' && !currentUser?.is_super_admin)} onClick={() => update(user, { active: !user.active })}>{user.active ? 'Deactivate' : 'Reactivate'}</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card icon="doc" title="Audit activity" description="Latest account, authorization, traceability and administrative events.">
        {!auditLog.data && auditLog.loading ? <LoadingState compact label="Loading audit activity…" /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Outcome</th></tr></thead>
              <tbody>{(auditLog.data?.events || []).map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.created_at).toLocaleString()}</td>
                  <td>{event.actor_email || 'System'}</td>
                  <td>{event.action}{event.details ? <small className="audit-details">{event.details}</small> : null}</td>
                  <td>{event.target_type ? `${event.target_type} · ${event.target_id || '—'}` : '—'}{event.actor_user_id && <small className="audit-details">{userNames.get(event.actor_user_id) || ''}</small>}</td>
                  <td>{event.outcome}</td>
                </tr>
              ))}{!(auditLog.data?.events || []).length && <tr><td colSpan="5">No audit events recorded.</td></tr>}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
