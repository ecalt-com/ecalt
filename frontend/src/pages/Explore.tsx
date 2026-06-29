import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Clock, BookOpen, Zap, Check, RefreshCw, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import Navigation from '../components/Navigation'
import CuriosityInput from '../components/CuriosityInput'
import StepNode from '../components/StepNode'
import StepUpgradePanel from '../components/StepUpgradePanel'
import { previewJourney, confirmJourney, markStepComplete, saveProfession, getUserProfile } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { usePageTitle } from '../lib/usePageTitle'
import type { Journey, JourneyStep, LearnerPurpose, TopicExpertise } from '../lib/types'

// ── Learner intent options ────────────────────────────────────────────────────

const PURPOSE_OPTIONS: { value: LearnerPurpose; label: string }[] = [
  { value: 'research_paper',      label: '📄 Research / thesis' },
  { value: 'professional_growth', label: '💼 Professional growth' },
  { value: 'personal_curiosity',  label: '🔭 General curiosity' },
  { value: 'teaching_others',     label: '🎓 Teaching others' },
  { value: 'fun',                 label: '🎮 Just for fun' },
]

const EXPERTISE_OPTIONS: { value: TopicExpertise; label: string }[] = [
  { value: 'beginner',     label: 'New to this' },
  { value: 'intermediate', label: 'Some background' },
  { value: 'advanced',     label: 'Solid knowledge' },
  { value: 'expert',       label: 'Domain expert' },
]

// ── Refinement options ────────────────────────────────────────────────────────

const ISSUE_OPTIONS: { value: string; label: string }[] = [
  { value: 'too_basic',      label: 'Too basic / surface level' },
  { value: 'too_advanced',   label: 'Too advanced / too dense' },
  { value: 'wrong_angle',    label: 'Wrong angle — different focus' },
  { value: 'wrong_topic',    label: 'Wrong topic — misunderstood me' },
  { value: 'missing_key',    label: 'Missing key concepts' },
]

const ISSUE_LABELS: Record<string, string> = {
  too_basic:    'Too basic / surface level',
  too_advanced: 'Too advanced / too dense',
  wrong_angle:  'Wrong angle — I needed a different focus',
  wrong_topic:  'Wrong topic — the question was misunderstood',
  missing_key:  'Missing key concepts',
}

// ── Phase state machine ───────────────────────────────────────────────────────
type ExplorePhase =
  | 'idle'
  | 'intent'           // collecting purpose + expertise before preview
  | 'loading'          // calling /preview
  | 'confirming'       // preview shown, awaiting user decision
  | 'refining'         // collecting structured feedback on rejected preview
  | 'confirming_save'  // calling /confirm
  | 'ready'            // confirmed + persisted, show full step list
  | 'error'

export default function Explore() {
  usePageTitle('Explore')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user, loading: authLoading, getToken } = useAuth()

  const [phase, setPhase] = useState<ExplorePhase>('idle')
  const [journey, setJourney] = useState<Journey | null>(null)
  const [steps, setSteps] = useState<JourneyStep[]>([])
  const [error, setError] = useState<string | null>(null)
  const [budgetExceeded, setBudgetExceeded] = useState(false)
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null)

  // Intent state
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [purpose, setPurpose] = useState<LearnerPurpose | null>(null)
  const [topicExpertise, setTopicExpertise] = useState<TopicExpertise | null>(null)
  const [professionInput, setProfessionInput] = useState('')
  const [professionSaved, setProfessionSaved] = useState(false)

  // Preview state
  const [previewToken, setPreviewToken] = useState<string | null>(null)

  // Refinement state
  const [prevJourneyTitle, setPrevJourneyTitle] = useState<string | null>(null)
  const [prevJourneyDesc,  setPrevJourneyDesc]  = useState<string | null>(null)
  const [refinementIssue,  setRefinementIssue]  = useState<string | null>(null)
  const [refinementText,   setRefinementText]   = useState('')
  const [refineCount,      setRefineCount]      = useState(0)

  const q = searchParams.get('q') || ''

  useEffect(() => {
    if (!authLoading && !user) navigate('/')
  }, [user, authLoading, navigate])

  // If we land with ?q=, check if we already have intent or go straight to intent modal
  useEffect(() => {
    if (q && user && phase === 'idle') {
      setPendingQuestion(q)
      setPhase('intent')
    }
  }, [q, user])

  // Pre-fill profession from user profile
  useEffect(() => {
    if (!user) return
    getToken().then(token => {
      if (!token) return
      getUserProfile(token).then(profile => {
        if (profile.profession) {
          setProfessionInput(profile.profession)
          setProfessionSaved(true)
        }
      }).catch(() => {})
    })
  }, [user])

  const handleQuestionSubmit = (question: string) => {
    setPendingQuestion(question)
    setPhase('intent')
  }

  const handleBuildJourney = async (skipIntent = false) => {
    const token = await getToken()
    if (!token) { navigate('/'); return }

    // Save profession if entered and not yet saved
    if (professionInput.trim() && !professionSaved) {
      saveProfession(professionInput.trim(), token).catch(() => {})
      setProfessionSaved(true)
    }

    setPhase('loading')
    setError(null)
    setBudgetExceeded(false)
    setJourney(null)
    setPreviewToken(null)

    try {
      const { preview_token, journey: result } = await previewJourney(
        {
          question: pendingQuestion,
          age_group: 'all',
          learner_purpose: skipIntent ? undefined : (purpose ?? undefined),
          topic_expertise: skipIntent ? undefined : (topicExpertise ?? undefined),
        },
        token,
      )
      setPreviewToken(preview_token)
      setJourney(result)
      setSteps(result.steps)
      setPrevJourneyTitle(result.title)
      setPrevJourneyDesc(result.description)
      setPhase('confirming')
    } catch (err: any) {
      if (err?.status === 402) {
        setBudgetExceeded(true)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to generate journey. Please try again.')
      }
      setPhase('error')
    }
  }

  const handleConfirm = async () => {
    if (!previewToken) return
    setPhase('confirming_save')
    const token = await getToken()
    if (!token) { navigate('/'); return }
    try {
      const { journey: confirmed } = await confirmJourney(previewToken, token)
      setJourney(confirmed)
      setSteps(confirmed.steps)
      setPhase('ready')
    } catch (err: any) {
      if (err?.status === 404) {
        // Preview expired — regenerate
        setError('Preview expired. Generating a fresh one…')
        setPhase('error')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to save journey. Please try again.')
        setPhase('error')
      }
    }
  }

  const handleRefine = () => {
    setRefinementIssue(null)
    setRefinementText('')
    setPhase('refining')
  }

  const handleRegenerate = async () => {
    const issue   = refinementIssue ? ISSUE_LABELS[refinementIssue] : ''
    const details = refinementText.trim()
    const ctx     = [issue, details].filter(Boolean).join('. ')

    const token = await getToken()
    if (!token) { navigate('/'); return }

    setPhase('loading')
    setRefineCount(c => c + 1)

    try {
      const { preview_token, journey: result } = await previewJourney(
        {
          question:           pendingQuestion,
          age_group:          'all',
          learner_purpose:    purpose ?? undefined,
          topic_expertise:    topicExpertise ?? undefined,
          refinement_context: ctx || undefined,
        },
        token,
      )
      setPreviewToken(preview_token)
      setJourney(result)
      setSteps(result.steps)
      setPrevJourneyTitle(result.title)
      setPrevJourneyDesc(result.description)
      setPhase('confirming')
    } catch (err: any) {
      if (err?.status === 402) {
        setBudgetExceeded(true)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to regenerate. Please try again.')
      }
      setPhase('error')
    }
  }

  const goExplore = (question: string) => {
    if (!question.trim()) {
      setPhase('idle')
      navigate('/explore')
      return
    }
    setPendingQuestion(question)
    setPhase('intent')
    navigate(`/explore?q=${encodeURIComponent(question)}`, { replace: true })
  }

  const isStepLocked = (index: number) => steps.slice(0, index).some(s => !s.completed)

  const completeStep = async (stepId: string) => {
    const index = steps.findIndex(s => s.id === stepId)
    if (index === -1 || !journey) return
    if (steps[index].completed || isStepLocked(index)) return
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: true } : s))
    const token = await getToken()
    if (token) {
      try {
        await markStepComplete(journey.id, stepId, token)
      } catch {
        setSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: false } : s))
      }
    }
  }

  const toggleExpanded = (stepId: string) =>
    setExpandedStepId(prev => (prev === stepId ? null : stepId))

  const beginJourney = () => {
    const target = steps.find(s => !s.completed) ?? steps[0]
    if (!target) return
    setExpandedStepId(target.id)
    document.getElementById(`step-${target.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const completed = steps.filter(s => s.completed).length
  const progress  = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0

  return (
    <>
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-violet-500/5 rounded-full blur-[120px] animate-glow-pulse" />
        <div className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-cyan-500/5 rounded-full blur-[100px] animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <Navigation />

      <div className="relative min-h-screen pt-24 pb-16 px-4">
        <div className="max-w-3xl mx-auto">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 mb-8 transition-colors group"
          >
            <ArrowLeft size={14} className="group-hover:-translate-x-0.5 transition-transform" />
            Back home
          </button>

          {/* ── Idle: question input ── */}
          {phase === 'idle' && (
            <div className="mb-12">
              <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100 mb-3">What do you want to learn?</h1>
              <p className="text-slate-500 mb-8">Ask anything — ECALT will build your learning path.</p>
              <CuriosityInput onExplore={handleQuestionSubmit} initialValue={q} />
            </div>
          )}

          {/* ── Intent modal ── */}
          {phase === 'intent' && (
            <div className="animate-in">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1">
                Quick profile
              </h1>
              <p className="text-slate-500 text-sm mb-8">
                Helps us calibrate the depth and tone of your journey. 10 seconds.
              </p>

              <div className="glass-card rounded-2xl p-6 space-y-6">
                {/* Profession */}
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Your background / profession
                    <span className="text-slate-400 font-normal ml-1">(optional)</span>
                  </p>
                  <input
                    type="text"
                    value={professionInput}
                    onChange={e => { setProfessionInput(e.target.value); setProfessionSaved(false) }}
                    placeholder="e.g. PhD Researcher in Physics, Software Engineer, High school student…"
                    className={clsx(
                      'w-full text-sm px-4 py-2.5 rounded-xl border transition-colors',
                      'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                      'border-slate-200 dark:border-slate-700',
                      'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                      'placeholder:text-slate-300 dark:placeholder:text-slate-600',
                    )}
                  />
                </div>

                {/* Purpose */}
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                    Why are you exploring this?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {PURPOSE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setPurpose(p => p === opt.value ? null : opt.value)}
                        className={clsx(
                          'px-3 py-1.5 rounded-full text-sm border transition-colors',
                          purpose === opt.value
                            ? 'bg-violet-600 text-white border-violet-600'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-violet-400 dark:hover:border-violet-500',
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Expertise */}
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                    Your familiarity with this topic
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {EXPERTISE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setTopicExpertise(e => e === opt.value ? null : opt.value)}
                        className={clsx(
                          'px-3 py-1.5 rounded-full text-sm border transition-colors',
                          topicExpertise === opt.value
                            ? 'bg-cyan-600 text-white border-cyan-600'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-cyan-400 dark:hover:border-cyan-500',
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => handleBuildJourney(false)}
                    className="btn-primary flex items-center gap-2"
                  >
                    <Zap size={14} fill="currentColor" />
                    Build my journey
                  </button>
                  <button
                    onClick={() => handleBuildJourney(true)}
                    className="btn-ghost text-sm"
                  >
                    Skip
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── Loading skeleton ── */}
          {phase === 'loading' && (
            <div className="space-y-5">
              <div className="shimmer-bg h-8 w-3/4 rounded-xl" />
              <div className="shimmer-bg h-5 w-full rounded-xl" />
              <div className="shimmer-bg h-5 w-2/3 rounded-xl" />
              <div className="flex gap-3 mt-4">
                {[24, 20, 28].map(w => <div key={w} className={`shimmer-bg h-7 w-${w} rounded-full`} />)}
              </div>
              <div className="mt-8 space-y-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex gap-4">
                    <div className="shimmer-bg w-10 h-10 rounded-full shrink-0" />
                    <div className="flex-1 space-y-2 pt-2">
                      <div className="shimmer-bg h-4 w-2/3 rounded-lg" />
                      <div className="shimmer-bg h-3 w-full rounded-lg" />
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-center text-sm text-slate-500 mt-4">✦ Building your learning journey…</p>
            </div>
          )}

          {/* ── Error ── */}
          {phase === 'error' && (
            <div className="glass rounded-2xl border border-rose-200 dark:border-rose-500/20">
              {budgetExceeded ? (
                <div className="p-6">
                  <StepUpgradePanel />
                </div>
              ) : (
                <div className="p-8 text-center">
                  <p className="text-rose-600 dark:text-rose-400 mb-4">{error}</p>
                  <div className="flex items-center justify-center gap-3">
                    <button onClick={() => handleBuildJourney(false)} className="btn-primary">Try again</button>
                    <button onClick={() => setPhase('idle')} className="btn-ghost">Start over</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Refining: structured feedback panel ── */}
          {phase === 'refining' && (
            <div className="animate-in">
              <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">
                Let's get this right
              </h2>
              <p className="text-sm text-slate-500 mb-6">
                Tell us what was off — we'll regenerate with your feedback.
              </p>

              {prevJourneyTitle && (
                <div className="glass-card rounded-xl p-4 mb-6 border-l-2 border-slate-300 dark:border-slate-600">
                  <p className="text-xs text-slate-500 mb-0.5 uppercase tracking-wide">We generated</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{prevJourneyTitle}</p>
                  {prevJourneyDesc && (
                    <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{prevJourneyDesc}</p>
                  )}
                </div>
              )}

              <div className="glass-card rounded-2xl p-6 space-y-5">
                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                    What was off?
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {ISSUE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setRefinementIssue(r => r === opt.value ? null : opt.value)}
                        className={clsx(
                          'px-3 py-1.5 rounded-full text-sm border transition-colors',
                          refinementIssue === opt.value
                            ? 'bg-rose-500 text-white border-rose-500'
                            : 'border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-rose-300 dark:hover:border-rose-500/50',
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Anything specific to add?
                    <span className="text-slate-400 font-normal ml-1">(optional)</span>
                  </p>
                  <textarea
                    rows={3}
                    value={refinementText}
                    onChange={e => setRefinementText(e.target.value)}
                    placeholder={
                      refinementIssue === 'wrong_angle'
                        ? 'e.g. "I wanted the mathematical formalism — Hilbert spaces and operators"'
                        : refinementIssue === 'wrong_topic'
                          ? 'e.g. "I meant the Penrose–Hawking singularity theorems specifically"'
                          : 'Tell us what you were really looking for…'
                    }
                    className={clsx(
                      'w-full text-sm px-4 py-2.5 rounded-xl border transition-colors resize-none',
                      'bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200',
                      'border-slate-200 dark:border-slate-700',
                      'focus:outline-none focus:border-violet-400 dark:focus:border-violet-500',
                      'placeholder:text-slate-300 dark:placeholder:text-slate-600',
                    )}
                  />
                </div>

                <div className="flex flex-col sm:flex-row gap-3 pt-1">
                  <button
                    onClick={handleRegenerate}
                    disabled={!refinementIssue && !refinementText.trim()}
                    className="btn-primary flex items-center justify-center gap-2"
                  >
                    <Zap size={14} fill="currentColor" />
                    Regenerate with this feedback
                  </button>
                  <button
                    onClick={() => { setPendingQuestion(''); setRefineCount(0); setPhase('idle') }}
                    className="btn-ghost text-sm"
                  >
                    Change question entirely
                  </button>
                </div>

                {refineCount > 0 && (
                  <p className="text-xs text-slate-400">
                    Refined {refineCount} time{refineCount > 1 ? 's' : ''} — each attempt uses a small AI credit.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Confirming: preview + confirmation banner ── */}
          {(phase === 'confirming' || phase === 'confirming_save') && journey && (
            <div className="animate-in">
              {/* Confirmation banner */}
              <div className="glass-card rounded-2xl p-5 border border-violet-200 dark:border-violet-500/30 mb-8">
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Does this match what you were looking for?
                </p>
                <p className="text-xs text-slate-500 mb-4">
                  Confirm to save and start — or refine your question.
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    onClick={handleConfirm}
                    disabled={phase === 'confirming_save'}
                    className="btn-primary flex items-center justify-center gap-2"
                  >
                    {phase === 'confirming_save'
                      ? <Loader2 size={14} className="animate-spin" />
                      : <Check size={14} />}
                    Yes, start this journey
                  </button>
                  <button
                    onClick={handleRefine}
                    disabled={phase === 'confirming_save'}
                    className="btn-ghost flex items-center gap-1.5"
                  >
                    <RefreshCw size={13} />
                    {refineCount > 0 ? 'Refine again' : 'Not quite — refine'}
                  </button>
                </div>
              </div>

              {/* Journey preview (read-only — no Begin button yet) */}
              <JourneyHeader journey={journey} steps={steps} progress={0} completed={0} showBegin={false} />

              <div className="flex items-center gap-3 mb-8">
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                <span className="text-xs text-slate-400 uppercase tracking-widest">Your Path</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
              </div>

              {steps.map((step, i) => (
                <StepNode
                  key={step.id}
                  step={step}
                  index={i}
                  isLast={i === steps.length - 1}
                  journeyId={journey.id}
                  getToken={getToken}
                  expanded={false}
                  onExpandToggle={() => {}}
                  locked={true}
                />
              ))}
            </div>
          )}

          {/* ── Ready: full journey ── */}
          {phase === 'ready' && journey && (
            <div className="animate-in">
              <JourneyHeader
                journey={journey}
                steps={steps}
                progress={progress}
                completed={completed}
                showBegin={true}
                onBegin={beginJourney}
                onAskElse={() => goExplore('')}
              />

              <div className="flex items-center gap-3 mb-8">
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
                <span className="text-xs text-slate-400 uppercase tracking-widest">Your Path</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-slate-800" />
              </div>

              {steps.map((step, i) => (
                <StepNode
                  key={step.id}
                  step={step}
                  index={i}
                  isLast={i === steps.length - 1}
                  journeyId={journey.id}
                  getToken={getToken}
                  onToggle={completeStep}
                  expanded={expandedStepId === step.id}
                  onExpandToggle={toggleExpanded}
                  locked={isStepLocked(i)}
                />
              ))}

              <div className="mt-16 pt-8 border-t border-slate-200 dark:border-slate-800/50">
                <p className="text-center text-slate-500 text-sm mb-6">Curious about something else?</p>
                <CuriosityInput onExplore={goExplore} />
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}


// ── Journey header (shared between confirming + ready phases) ─────────────────

interface JourneyHeaderProps {
  journey: Journey
  steps: JourneyStep[]
  progress: number
  completed: number
  showBegin: boolean
  onBegin?: () => void
  onAskElse?: () => void
}

function JourneyHeader({ journey, steps, progress, completed, showBegin, onBegin, onAskElse }: JourneyHeaderProps) {
  return (
    <div className="mb-10">
      <div className="flex items-start gap-3 mb-4">
        <span className="text-4xl sm:text-5xl shrink-0">{journey.icon}</span>
        <div>
          <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Learning Journey</p>
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight">
            {journey.title}
          </h1>
        </div>
      </div>
      <p className="text-slate-500 leading-relaxed mb-5">{journey.description}</p>

      <div className="flex flex-wrap gap-2 mb-5">
        <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
          <BookOpen size={11} />{steps.length} steps
        </span>
        <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100/60 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400">
          <Clock size={11} />~{journey.estimated_hours}h
        </span>
        <span className="px-3 py-1.5 rounded-full text-xs border border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-300 capitalize">
          {journey.difficulty}
        </span>
        {journey.tags.map(tag => (
          <span key={tag} className="px-3 py-1.5 rounded-full text-xs border border-slate-200 bg-slate-100 text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-600">#{tag}</span>
        ))}
      </div>

      {completed > 0 && (
        <div className="mb-5">
          <div className="flex justify-between text-xs text-slate-500 mb-1.5">
            <span>{completed} of {steps.length} steps complete</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-violet-600 to-cyan-500 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {showBegin && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <button onClick={onBegin} className="btn-primary flex items-center justify-center gap-2">
            <Zap size={14} fill="currentColor" />Begin Journey
          </button>
          <button onClick={onAskElse} className="btn-ghost text-center">Ask something else</button>
        </div>
      )}
    </div>
  )
}
