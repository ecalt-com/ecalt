import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Loader2, ArrowLeft, Flame, BookOpen, Brain, MessageCircle, CheckCircle2,
  Download, Trash2, AlertTriangle, X, ShieldCheck, Undo2, FileText, RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { useAuth } from '../lib/AuthContext'
import { useToast } from '../lib/ToastContext'
import { apiErrorCode } from '../lib/api'
import {
  getChildren, getChildOverview, getChildActivity, getChildTranscript, getChildConsentRecord,
  patchChildSettings, revokeChildConsent, cancelChildRevocation, reconsentChild,
  exportChildData, deleteChild,
  type ChildOverview, type ChildActivity, type ChildTranscript, type ChildConsentRecord,
  type ChildSettings, type ContentAgeBand, type TranscriptVisibility,
} from '../lib/familyApi'

type Tab = 'overview' | 'activity' | 'consent' | 'settings'

const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'

const fmtDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—'

function downloadJson(data: unknown, filename: string) {
  const blob = data instanceof Blob ? data : new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function FamilyChild() {
  const { uid } = useParams<{ uid: string }>()
  const { user, loading: authLoading, getToken } = useAuth()
  const navigate = useNavigate()

  const [tab, setTab] = useState<Tab>('overview')
  const [overview, setOverview] = useState<ChildOverview | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Revocation state is in-session only — the list endpoint has no
  // "deletion scheduled" field yet, so we track it from the revoke response.
  const [revokePending, setRevokePending] = useState(false)
  const [revokeMessage, setRevokeMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true })
  }, [authLoading, user, navigate])

  const loadOverview = useCallback(async () => {
    if (!uid) return
    const token = await getToken()
    if (!token) return
    try {
      setOverview(await getChildOverview(uid, token))
      setLoadError(null)
    } catch (err: unknown) {
      setLoadError((err as { status?: number })?.status === 403
        ? "This child isn't linked to your family."
        : "Couldn't load this child's details.")
    }
  }, [uid, getToken])

  useEffect(() => {
    if (user) loadOverview()
  }, [user, loadOverview])

  if (authLoading || !user || !uid) {
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center">
        <Loader2 className="animate-spin text-violet-500" />
      </div>
    )
  }

  const name = overview?.child.display_name || 'Child'

  return (
    <>
      <PageMeta title={`${name} — Family`} description="Your child's learning overview, activity and settings." />
      <Navigation />
      <div className="min-h-screen bg-[var(--bg-primary)] pt-24 pb-16 px-4">
        <div className="max-w-2xl mx-auto">
          <Link to="/family" className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-violet-600 dark:hover:text-violet-400 mb-4">
            <ArrowLeft size={13} /> Family dashboard
          </Link>

          {loadError && (
            <div className="glass-card rounded-2xl p-5 text-sm text-rose-600 dark:text-rose-400">{loadError}</div>
          )}

          {!overview && !loadError && (
            <div className="flex justify-center py-16"><Loader2 className="animate-spin text-violet-500" /></div>
          )}

          {overview && (
            <>
              <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{name}</h1>
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded-full',
                  overview.child.paused || revokePending
                    ? 'bg-slate-100 text-slate-500 dark:bg-slate-700/50 dark:text-slate-400'
                    : overview.child.account_status === 'active'
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
                )}>
                  {revokePending ? 'Deletion scheduled' : overview.child.paused ? 'Paused' : overview.child.account_status === 'active' ? 'Active' : 'Awaiting verification'}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
                Last active {fmtDate(overview.child.last_active_date)} · joined {fmtDate(overview.child.created_at)}
              </p>

              {revokePending && (
                <RevocationBanner
                  uid={uid}
                  message={revokeMessage}
                  onRestored={() => { setRevokePending(false); setRevokeMessage(null); loadOverview() }}
                />
              )}

              <div className="flex gap-1 mb-5 glass rounded-xl p-1">
                {(['overview', 'activity', 'consent', 'settings'] as Tab[]).map(t => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={clsx(
                      'flex-1 px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-all',
                      tab === t
                        ? 'bg-violet-50 text-violet-700 dark:bg-violet-600/20 dark:text-violet-300'
                        : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>

              {tab === 'overview' && <OverviewTab overview={overview} />}
              {tab === 'activity' && <ActivityTab uid={uid} />}
              {tab === 'consent' && <ConsentTab uid={uid} childName={name} />}
              {tab === 'settings' && (
                <SettingsTab
                  uid={uid}
                  childName={name}
                  onRevoked={(msg) => { setRevokePending(true); setRevokeMessage(msg) }}
                  onPausedChange={loadOverview}
                />
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

// ── Revocation countdown banner with undo ────────────────────────────────────

function RevocationBanner({ uid, message, onRestored }: { uid: string; message: string | null; onRestored: () => void }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [cancelling, setCancelling] = useState(false)

  const handleUndo = async () => {
    setCancelling(true)
    try {
      const token = await getToken()
      if (!token) return
      await cancelChildRevocation(uid, token)
      addToast('Revocation cancelled — account restored ✓')
      onRestored()
    } catch (err: unknown) {
      if (apiErrorCode(err) === 'nothing_scheduled') {
        addToast('No deletion was scheduled.', 'info')
        onRestored()
      } else {
        addToast("Couldn't cancel the revocation. Please try again.", 'error')
      }
    } finally {
      setCancelling(false)
    }
  }

  return (
    <div className="mb-5 rounded-2xl border border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 p-4 flex items-center justify-between gap-3 flex-wrap">
      <p className="text-xs text-rose-700 dark:text-rose-300">
        {message ?? 'Consent withdrawn — the account is paused now and will be deleted in 14 days.'}
      </p>
      <button
        onClick={handleUndo}
        disabled={cancelling}
        className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-rose-300 dark:border-rose-500/40 text-rose-700 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-500/20 transition-all disabled:opacity-60"
      >
        {cancelling ? <Loader2 size={12} className="animate-spin" /> : <Undo2 size={12} />}
        Undo
      </button>
    </div>
  )
}

// ── Overview tab ──────────────────────────────────────────────────────────────

function OverviewTab({ overview }: { overview: ChildOverview }) {
  const quizAccuracy = overview.quiz.total > 0
    ? Math.round((overview.quiz.correct / overview.quiz.total) * 100)
    : null

  const stats = [
    { icon: Flame, label: 'Streak', value: `${overview.child.streak_days} days` },
    { icon: CheckCircle2, label: 'Steps completed', value: String(overview.totals.steps_completed) },
    { icon: Brain, label: 'Quiz accuracy', value: quizAccuracy !== null ? `${quizAccuracy}%` : '—' },
    { icon: BookOpen, label: 'Knowledge topics', value: String(overview.totals.knowledge_nodes) },
  ]

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {stats.map(({ icon: Icon, label, value }) => (
          <div key={label} className="glass-card rounded-2xl p-4 text-center">
            <Icon size={16} className="mx-auto mb-1.5 text-violet-500" />
            <p className="text-lg font-bold text-slate-900 dark:text-slate-100">{value}</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">{label}</p>
          </div>
        ))}
      </div>

      {overview.top_domains.length > 0 && (
        <div className="glass-card rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Strongest areas</h2>
          <div className="flex flex-wrap gap-2">
            {overview.top_domains.map(d => (
              <span key={d.domain} className="text-xs px-2.5 py-1 rounded-full bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300 capitalize">
                {d.domain} · {d.concept_count} topics
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Recent journeys</h2>
        {overview.recent_journeys.length === 0 ? (
          <p className="text-xs text-slate-400">No journeys yet.</p>
        ) : (
          <div className="space-y-3">
            {overview.recent_journeys.map(j => {
              const pct = j.total_steps > 0 ? Math.round((j.completed_steps / j.total_steps) * 100) : 0
              return (
                <div key={j.id}>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <p className="text-sm text-slate-800 dark:text-slate-200 truncate">
                      {j.icon ? `${j.icon} ` : ''}{j.title}
                    </p>
                    <span className="text-xs text-slate-400 shrink-0">{j.completed_steps}/{j.total_steps} steps</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/50 overflow-hidden">
                    <div className="h-full rounded-full bg-violet-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Activity tab ──────────────────────────────────────────────────────────────

function ActivityTab({ uid }: { uid: string }) {
  const { getToken } = useAuth()
  const [days, setDays] = useState(30)
  const [activity, setActivity] = useState<ChildActivity | null>(null)
  const [loading, setLoading] = useState(true)
  const [transcript, setTranscript] = useState<ChildTranscript | null>(null)
  const [transcriptLoading, setTranscriptLoading] = useState<string | null>(null)
  const { addToast } = useToast()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        const data = await getChildActivity(uid, days, token)
        if (!cancelled) setActivity(data)
      } catch {
        if (!cancelled) setActivity(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [uid, days, getToken])

  const openTranscript = async (conversationId: string) => {
    setTranscriptLoading(conversationId)
    try {
      const token = await getToken()
      if (!token) return
      setTranscript(await getChildTranscript(uid, conversationId, token))
    } catch (err: unknown) {
      addToast(
        apiErrorCode(err) === 'transcripts_not_enabled'
          ? 'Transcripts are not enabled for this child — turn on "Conversation access: full" in Settings.'
          : "Couldn't load the conversation.",
        'error',
      )
    } finally {
      setTranscriptLoading(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Activity</h2>
        <select
          value={days}
          onChange={e => setDays(Number(e.target.value))}
          className="px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-300 focus:outline-none"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading && <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>}
      {!loading && !activity && <p className="text-sm text-rose-500">Couldn't load activity.</p>}

      {!loading && activity && (
        <>
          <div className="glass-card rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Journeys started ({activity.journeys_started.length})</h3>
            {activity.journeys_started.length === 0
              ? <p className="text-xs text-slate-400">None in this period.</p>
              : activity.journeys_started.map(j => (
                <div key={j.id} className="py-1.5 border-b border-slate-100 dark:border-slate-700/40 last:border-0">
                  <p className="text-sm text-slate-800 dark:text-slate-200">{j.title}</p>
                  <p className="text-[11px] text-slate-400">{fmtDateTime(j.created_at)}{j.question ? ` · asked: "${j.question}"` : ''}</p>
                </div>
              ))}
          </div>

          <div className="glass-card rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Steps completed ({activity.steps_completed.length})</h3>
            {activity.steps_completed.length === 0
              ? <p className="text-xs text-slate-400">None in this period.</p>
              : activity.steps_completed.slice(0, 25).map((s, i) => (
                <div key={`${s.step_id}-${i}`} className="py-1.5 border-b border-slate-100 dark:border-slate-700/40 last:border-0 flex items-center justify-between gap-2">
                  <p className="text-sm text-slate-800 dark:text-slate-200 truncate">{s.journey_title}</p>
                  <span className="text-[11px] text-slate-400 shrink-0">{fmtDateTime(s.completed_at)}</span>
                </div>
              ))}
          </div>

          <div className="glass-card rounded-2xl p-5">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Quizzes ({activity.quiz_answers.length})</h3>
            {activity.quiz_answers.length === 0
              ? <p className="text-xs text-slate-400">None in this period.</p>
              : activity.quiz_answers.slice(0, 25).map((q, i) => (
                <div key={i} className="py-1.5 border-b border-slate-100 dark:border-slate-700/40 last:border-0 flex items-center justify-between gap-2">
                  <p className="text-sm text-slate-800 dark:text-slate-200 truncate">
                    <span className={q.is_correct ? 'text-emerald-500' : 'text-rose-400'}>{q.is_correct ? '✓' : '✗'}</span>{' '}
                    {q.concept}
                  </p>
                  <span className="text-[11px] text-slate-400 shrink-0">{fmtDateTime(q.answered_at)}</span>
                </div>
              ))}
          </div>

          <div className="glass-card rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">AI conversations ({activity.conversations.length})</h3>
              {!activity.transcripts_available && (
                <span className="text-[11px] text-slate-400">titles only</span>
              )}
            </div>
            {activity.conversations.length === 0
              ? <p className="text-xs text-slate-400">None in this period.</p>
              : activity.conversations.map(c => (
                <div key={c.id} className="py-1.5 border-b border-slate-100 dark:border-slate-700/40 last:border-0 flex items-center justify-between gap-2">
                  {activity.transcripts_available ? (
                    <button
                      onClick={() => openTranscript(c.id)}
                      className="text-sm text-violet-600 dark:text-violet-400 hover:underline truncate text-left flex items-center gap-1.5"
                    >
                      {transcriptLoading === c.id && <Loader2 size={11} className="animate-spin shrink-0" />}
                      {c.title || 'Untitled conversation'}
                    </button>
                  ) : (
                    <p className="text-sm text-slate-800 dark:text-slate-200 truncate flex items-center gap-1.5">
                      <MessageCircle size={13} className="text-slate-400 shrink-0" />
                      {c.title || 'Untitled conversation'}
                    </p>
                  )}
                  <span className="text-[11px] text-slate-400 shrink-0">{c.message_count} messages</span>
                </div>
              ))}
          </div>
        </>
      )}

      {transcript && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="glass-card rounded-3xl p-6 max-w-lg w-full shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{transcript.title || 'Conversation'}</h3>
                <p className="text-[11px] text-slate-400">{fmtDateTime(transcript.started_at)}</p>
              </div>
              <button onClick={() => setTranscript(null)} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                <X size={16} />
              </button>
            </div>
            <div className="overflow-y-auto space-y-3 pr-1">
              {transcript.messages.map((m, i) => (
                <div key={i} className={clsx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
                  <div className={clsx(
                    'max-w-[85%] px-3 py-2 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap',
                    m.role === 'user'
                      ? 'bg-violet-600 text-white rounded-tr-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-tl-sm',
                  )}>
                    {m.content}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Consent tab ───────────────────────────────────────────────────────────────

const EVENT_LABELS: Record<string, string> = {
  requested: 'Consent requested',
  granted: 'Consent granted',
  refused: 'Consent declined',
  revoked: 'Consent withdrawn',
  reconsented: 'Policy re-accepted',
  reported: 'Approval disputed ("this wasn\'t me")',
  restored: 'Account restored',
}

const METHOD_LABELS: Record<string, string> = {
  signup: 'at signup',
  email_link: 'by email link',
  email_link_authenticated: 'by signed-in approval',
  parent_created: 'by parent-created account',
  card_verification: 'by card verification',
  parent_dashboard: 'from the Family dashboard',
}

function ConsentTab({ uid, childName }: { uid: string; childName: string }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [record, setRecord] = useState<ChildConsentRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [reconsenting, setReconsenting] = useState(false)

  const load = useCallback(async () => {
    const token = await getToken()
    if (!token) return
    try {
      setRecord(await getChildConsentRecord(uid, token))
    } catch { /* rendered below */ } finally {
      setLoading(false)
    }
  }, [uid, getToken])

  useEffect(() => { load() }, [load])

  const needsReconsent = record !== null
    && record.consent.consent_version !== null
    && record.consent.consent_version !== record.current_policy_version

  const handleReconsent = async () => {
    setReconsenting(true)
    try {
      const token = await getToken()
      if (!token) return
      await reconsentChild(uid, token)
      addToast('Policy re-accepted ✓')
      load()
    } catch {
      addToast("Couldn't record the re-consent. Please try again.", 'error')
    } finally {
      setReconsenting(false)
    }
  }

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>
  if (!record) return <p className="text-sm text-rose-500">Couldn't load the consent record.</p>

  return (
    <div className="space-y-5">
      {needsReconsent && (
        <div className="rounded-2xl border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4 flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs text-amber-800 dark:text-amber-300">
            Our privacy policy has been updated (v{record.current_policy_version}).{' '}
            <a href="/privacy-policy" target="_blank" rel="noopener noreferrer" className="underline">Review it</a>{' '}
            and re-accept for {childName}.
          </p>
          <button
            onClick={handleReconsent}
            disabled={reconsenting}
            className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-600 hover:bg-amber-500 text-white transition-all disabled:opacity-60"
          >
            {reconsenting ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Re-accept policy
          </button>
        </div>
      )}

      <div className="glass-card rounded-2xl p-5">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Current consent</h3>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Status</dt><dd className="text-slate-800 dark:text-slate-200 capitalize">{record.consent.account_status.replace(/_/g, ' ')}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Granted</dt><dd className="text-slate-800 dark:text-slate-200">{fmtDate(record.consent.consent_given_at)}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Policy version</dt><dd className="text-slate-800 dark:text-slate-200">{record.consent.consent_version ?? '—'} (current: {record.current_policy_version})</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Jurisdiction</dt><dd className="text-slate-800 dark:text-slate-200">{record.consent.jurisdiction ?? '—'}</dd></div>
          <div className="flex justify-between gap-2">
            <dt className="text-slate-500">Verification</dt>
            <dd className="text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
              {record.verification.verification_status === 'verified' && <ShieldCheck size={13} className="text-emerald-500" />}
              {record.verification.verification_tier === 'card' ? 'Card check' : record.verification.verification_tier === 'id' ? 'ID verification' : 'Email'}
              {' · '}{record.verification.verification_status ?? 'unverified'}
            </dd>
          </div>
        </dl>
      </div>

      <div className="glass-card rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Consent history</h3>
          <button
            onClick={() => downloadJson(record, `ecalt-consent-record-${uid}.json`)}
            className="inline-flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 hover:underline"
          >
            <FileText size={12} /> Download record
          </button>
        </div>
        {record.events.length === 0 ? (
          <p className="text-xs text-slate-400">No events recorded.</p>
        ) : (
          <ol className="space-y-2.5">
            {record.events.map((e, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" />
                <div>
                  <p className="text-slate-800 dark:text-slate-200">
                    {EVENT_LABELS[e.action] ?? e.action}
                    {e.method ? ` — ${METHOD_LABELS[e.method] ?? e.method}` : ''}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {fmtDate(e.created_at)}{e.policy_version ? ` · policy v${e.policy_version}` : ''}{e.jurisdiction ? ` · ${e.jurisdiction}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

// ── Settings tab (controls + danger zone) ─────────────────────────────────────

function SettingsTab({
  uid, childName, onRevoked, onPausedChange,
}: {
  uid: string
  childName: string
  onRevoked: (message: string | null) => void
  onPausedChange: () => void
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [settings, setSettings] = useState<ChildSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [showRevokeModal, setShowRevokeModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  // There is no per-child settings GET — the values live on the children list.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const token = await getToken()
      if (!token) return
      try {
        const { children } = await getChildren(token)
        const child = children.find(c => c.child_uid === uid)
        if (!cancelled && child) {
          setSettings({
            paused: Boolean(child.paused),
            chat_enabled: child.chat_enabled ?? true,
            content_age_band: child.content_age_band,
            transcript_visibility: child.transcript_visibility ?? 'summaries',
            weekly_digest_enabled: child.weekly_digest_enabled ?? true,
          })
        }
      } catch { /* rendered below */ } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [uid, getToken])

  const patch = async (change: Partial<ChildSettings>) => {
    setSaving(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await patchChildSettings(uid, change, token)
      setSettings(res.settings)
      if ('paused' in change) onPausedChange()
    } catch {
      addToast("Couldn't save the setting. Please try again.", 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const token = await getToken()
      if (!token) return
      downloadJson(await exportChildData(uid, token), `ecalt-${childName.toLowerCase()}-data-export.json`)
    } catch {
      addToast("Couldn't export the data. Please try again.", 'error')
    } finally {
      setExporting(false)
    }
  }

  if (loading) return <div className="flex justify-center py-10"><Loader2 className="animate-spin text-violet-500" /></div>
  if (!settings) return <p className="text-sm text-rose-500">Couldn't load the settings.</p>

  return (
    <div className="space-y-5">
      <div className="glass-card rounded-2xl p-5 space-y-5">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Parental controls</h3>

        <SettingToggle
          label="Pause account"
          description={`${childName} can't use ECALT at all while paused.`}
          on={settings.paused}
          disabled={saving}
          onToggle={v => patch({ paused: v })}
        />
        <SettingToggle
          label="AI chat"
          description="Allows the chat panel and the journey tutor."
          on={settings.chat_enabled}
          disabled={saving}
          onToggle={v => patch({ chat_enabled: v })}
        />
        <SettingToggle
          label="Weekly digest"
          description="A Sunday email summarizing what they learned."
          on={settings.weekly_digest_enabled}
          disabled={saving}
          onToggle={v => patch({ weekly_digest_enabled: v })}
        />

        <div>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200 mb-1">Content level</p>
          <p className="text-xs text-slate-500 mb-2">Overrides the age band used when generating journeys.</p>
          <select
            value={settings.content_age_band ?? ''}
            onChange={e => patch({ content_age_band: (e.target.value || null) as ContentAgeBand | null })}
            disabled={saving}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:border-violet-400"
          >
            <option value="">Automatic (based on age)</option>
            <option value="kids">Kids</option>
            <option value="teens">Teens</option>
            <option value="adults">Adults</option>
            <option value="all">All levels</option>
          </select>
        </div>

        <div>
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200 mb-1">Conversation access</p>
          <p className="text-xs text-slate-500 mb-2">
            "Full" lets you open their AI chat transcripts. {childName} is told what you can see either way.
          </p>
          <select
            value={settings.transcript_visibility}
            onChange={e => patch({ transcript_visibility: e.target.value as TranscriptVisibility })}
            disabled={saving}
            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm text-slate-800 dark:text-slate-200 focus:outline-none focus:border-violet-400"
          >
            <option value="summaries">Titles and counts only</option>
            <option value="full">Full transcripts</option>
          </select>
        </div>
      </div>

      {/* Danger zone */}
      <div className="glass-card rounded-2xl p-5 border border-rose-200 dark:border-rose-900/40">
        <h3 className="text-xs font-semibold text-rose-500 uppercase tracking-wide mb-4">Danger zone</h3>
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200">Download {childName}'s data</p>
              <p className="text-xs text-slate-500">Everything we store, as a JSON file.</p>
            </div>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-60"
            >
              {exporting ? <Loader2 size={11} className="animate-spin" /> : <Download size={11} />} Download
            </button>
          </div>

          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200">Withdraw consent</p>
              <p className="text-xs text-slate-500">Pauses the account now; deletes it in 14 days. You can undo within the window.</p>
            </div>
            <button
              onClick={() => setShowRevokeModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-rose-300 dark:border-rose-500/40 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-900/20 transition-all"
            >
              <AlertTriangle size={11} /> Withdraw
            </button>
          </div>

          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200">Delete {childName}'s account</p>
              <p className="text-xs text-slate-500">Immediately and permanently deletes everything.</p>
            </div>
            <button
              onClick={() => setShowDeleteModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all"
            >
              <Trash2 size={11} /> Delete
            </button>
          </div>
        </div>
      </div>

      {showRevokeModal && (
        <RevokeModal
          uid={uid}
          childName={childName}
          onExport={handleExport}
          exporting={exporting}
          onClose={() => setShowRevokeModal(false)}
          onRevoked={(msg) => { setShowRevokeModal(false); onRevoked(msg) }}
        />
      )}
      {showDeleteModal && (
        <DeleteChildModal uid={uid} childName={childName} onClose={() => setShowDeleteModal(false)} />
      )}
    </div>
  )
}

function SettingToggle({
  label, description, on, disabled, onToggle,
}: {
  label: string
  description: string
  on: boolean
  disabled?: boolean
  onToggle: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{label}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
      <button
        onClick={() => onToggle(!on)}
        disabled={disabled}
        role="switch"
        aria-checked={on}
        aria-label={label}
        className={clsx(
          'shrink-0 w-11 h-6 rounded-full relative transition-colors',
          on ? 'bg-violet-600' : 'bg-slate-300 dark:bg-slate-700',
          disabled && 'opacity-50',
        )}
      >
        <span className={clsx(
          'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform',
          on && 'translate-x-5',
        )} />
      </button>
    </div>
  )
}

function RevokeModal({
  uid, childName, onExport, exporting, onClose, onRevoked,
}: {
  uid: string
  childName: string
  onExport: () => void
  exporting: boolean
  onClose: () => void
  onRevoked: (message: string | null) => void
}) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const [revoking, setRevoking] = useState(false)

  const handleRevoke = async () => {
    setRevoking(true)
    try {
      const token = await getToken()
      if (!token) return
      const res = await revokeChildConsent(uid, token)
      onRevoked(res.message ?? null)
    } catch (err: unknown) {
      if (apiErrorCode(err) === 'already_scheduled') {
        onRevoked(null)
      } else {
        addToast("Couldn't withdraw consent. Please try again.", 'error')
        setRevoking(false)
      }
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle size={18} className="text-rose-500" />
          <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">Withdraw consent for {childName}?</h2>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
          Their account is paused immediately and permanently deleted in 14 days —
          journeys, progress, and conversations included. You can undo within that window.
        </p>
        <button
          onClick={onExport}
          disabled={exporting}
          className="w-full mb-4 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-violet-300 dark:hover:border-violet-600 transition-all disabled:opacity-60"
        >
          {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
          Download their data first
        </button>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleRevoke}
            disabled={revoking}
            className="flex-1 px-4 py-2 rounded-xl text-sm font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {revoking ? <Loader2 size={14} className="animate-spin" /> : 'Withdraw consent'}
          </button>
        </div>
      </div>
    </div>
  )
}

function DeleteChildModal({ uid, childName, onClose }: { uid: string; childName: string; onClose: () => void }) {
  const { getToken } = useAuth()
  const { addToast } = useToast()
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (input !== 'DELETE') return
    setDeleting(true)
    try {
      const token = await getToken()
      if (!token) return
      await deleteChild(uid, token)
      addToast(`${childName}'s account has been deleted.`)
      navigate('/family', { replace: true })
    } catch {
      addToast("Couldn't delete the account. Please try again.", 'error')
      setDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/70 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="glass-card rounded-3xl p-6 sm:p-8 max-w-sm w-full shadow-2xl">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-rose-500" />
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">Delete {childName}'s account?</h2>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X size={16} />
          </button>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">
          This permanently deletes all of {childName}'s journeys, progress and conversations —
          and withdraws your consent.
        </p>
        <p className="text-xs font-semibold text-rose-600 dark:text-rose-400 mb-4">This cannot be undone.</p>
        <div className="mb-4">
          <label htmlFor="delete-child-confirm" className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
            Type DELETE to confirm:
          </label>
          <input
            id="delete-child-confirm"
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            className="w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:border-rose-400"
          />
        </div>
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-xl text-sm font-medium border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            disabled={input !== 'DELETE' || deleting}
            className="flex-1 px-4 py-2 rounded-xl text-sm font-medium bg-rose-600 hover:bg-rose-500 text-white transition-all disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}
