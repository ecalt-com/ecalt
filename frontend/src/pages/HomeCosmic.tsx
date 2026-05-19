import '../styles/cosmic.css'
import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Zap, Loader2 } from 'lucide-react'
import GateModal from '../components/GateModal'
import Navigation from '../components/Navigation'
import PageMeta from '../components/PageMeta'
import { askSpark, getSessionStatus, getPassport, getUserProfile, type PassportData } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import type { Mission } from '../lib/types'

// ── Session ───────────────────────────────────────────────────────────────────
function getSessionId() {
  let id = localStorage.getItem('ecalt_sid') || ''
  if (!id) { id = crypto.randomUUID(); localStorage.setItem('ecalt_sid', id) }
  return id
}

// ── Phase (mirrors Home.tsx) ──────────────────────────────────────────────────
type Phase =
  | { kind: 'hero' }
  | { kind: 'loading'; question: string }
  | { kind: 'sparked'; question: string; answer: string; mission: Mission; sparksUsed: number; sparksRemaining: number }
  | { kind: 'error'; question: string; message: string }

type RecentJourney = PassportData['journeys'][0]

// ── Field data ────────────────────────────────────────────────────────────────
const FIELD_DATA: Record<string, { years: string; insight: string; sub: string }> = {
  medicine:    { years: '25–40', insight: 'The gut-brain axis — how your digestive system directly affects mood, cognition and immune response', sub: 'Discovered in the 1990s. Still not taught in most medical schools. Psychiatrists and gastroenterologists still rarely talk to each other.' },
  finance:     { years: '30–50', insight: 'Behavioural finance — why markets consistently defy rational models and what actually drives prices', sub: "Kahneman's work earned a Nobel in 2002. Standard finance education still teaches efficient market hypothesis as settled truth." },
  engineering: { years: '15–30', insight: 'Complex systems and emergence — why engineered systems fail in ways their designers never anticipated', sub: 'Systems thinking has transformed aerospace and infrastructure safety. Still treated as a niche subspecialty in most engineering programmes.' },
  law:         { years: '20–40', insight: 'Empirical legal studies — what legal outcomes actually correlate with, versus what doctrine says they should', sub: 'Judges decide differently based on time of day, meal breaks, and prior cases. Decades of research. Almost no influence on legal education.' },
  education:   { years: '40–60', insight: 'Spaced repetition, retrieval practice and interleaving — how memory actually consolidates versus how schools schedule learning', sub: 'Cognitive science has known the optimal learning schedule since the 1970s. Schools still organise around semester blocks and unit tests.' },
  psychology:  { years: '20–35', insight: 'Embodied cognition — how your posture, movement and environment directly shape your thoughts and decisions', sub: 'Your body does not just carry your brain. It participates in thinking. Proven across hundreds of studies. Rarely taught outside specialist journals.' },
  design:      { years: '15–25', insight: 'Affordances and mental models — why people consistently fail to use well-designed products and what design actually controls', sub: 'Don Norman described this in 1988. Most design education still treats it as optional theory rather than foundational practice.' },
  climate:     { years: '10–20', insight: 'Tipping points and irreversibility — where in the system the real risks are, and why linear projections miss them', sub: 'Climate science has moved beyond temperature averages to cascade effects. The public conversation is still catching up to where scientists were a decade ago.' },
  biology:     { years: '20–40', insight: 'Epigenetics — how lived experience changes gene expression without altering the genetic code, and how this passes to offspring', sub: 'Lamarck was wrong about inheritance, but the mechanism he intuited turned out to be real. Standard biology education still does not reflect this fully.' },
  business:    { years: '15–30', insight: 'Organisational psychology and the science of motivation — why standard management practices consistently undermine the performance they seek', sub: "Deci and Ryan's Self-Determination Theory has been replicated hundreds of times. Most MBA programmes still teach incentive-based management as primary." },
  art:         { years: '20–35', insight: 'Predictive processing — how the brain actively constructs perception and what this means for how aesthetic experience actually works', sub: 'Neuroscience of art is one of the most exciting intersections in contemporary research. Almost entirely absent from art education.' },
  computing:   { years: '30–50', insight: 'Information theory and the mathematical limits of knowledge — what can and cannot be computed, and why this matters for everything AI does', sub: "Shannon's 1948 paper underlies all of modern computing. Most software engineers have never read it and do not know what it implies for AI capabilities." },
}

const FIELD_TAGS = ['Medicine','Finance','Engineering','Law','Education','Psychology','Design','Climate','Biology','Business','Art','Computing']

function normaliseField(s: string): string {
  const lower = s.toLowerCase().trim()
  return Object.keys(FIELD_DATA).find(k => lower.includes(k) || k.includes(lower)) ?? 'computing'
}

// ── Timeline data ─────────────────────────────────────────────────────────────
const TIMELINE_EVENTS = [
  { side: 'left'  as const, year: '1847 — 1890', field: 'Medicine',         discovery: 'Germs cause disease',                                    gap: 'Semmelweis proved handwashing saves lives. Doctors dismissed him. He died in an asylum.',                                                           delay: '40 years to reach hospitals',       lit: false },
  { side: 'right' as const, year: '1905 — 1960', field: 'Physics',           discovery: 'Time is not constant. It bends.',                         gap: "Einstein's relativity. GPS satellites would fail without it. Taught in schools as advanced physics only.",                                          delay: '55 years to reach engineering',     lit: false },
  { side: 'left'  as const, year: '1960 — now',  field: 'Psychology',        discovery: 'The brain can physically rewire itself at any age',        gap: 'Neuroplasticity. Proven in the 1960s. Still not reflected in most school curricula or parenting advice.',                                          delay: '60+ years, still arriving',         lit: false },
  { side: 'right' as const, year: '1983 — 2015', field: 'Economics',         discovery: 'Humans are systematically irrational — and predictably so',gap: "Kahneman and Tversky's behavioural economics. Nobel Prize 2002. Still not taught in standard economics courses.",                                  delay: '32 years to reach policy',          lit: false },
  { side: 'left'  as const, year: '1943 — 2017', field: 'Computer Science',  discovery: 'Intelligence can emerge from patterns, not rules',         gap: 'Neural networks were theorised in 1943. Ignored for 40 years. Now reshaping every industry — still untaught at most universities.',              delay: '70+ years to reach mainstream',     lit: false },
  { side: 'right' as const, year: 'Right now',   field: 'Every Field',       discovery: 'Discoveries waiting for you to receive them',              gap: 'The frontier of human understanding is further ahead than most people realise. ECALT closes your personal light delay.',                           delay: 'Your gap — measured below',         lit: true,  active: true },
]

// ── Custom cursor ─────────────────────────────────────────────────────────────
function CustomCursor() {
  const dotRef  = useRef<HTMLDivElement>(null)
  const ringRef = useRef<HTMLDivElement>(null)
  const mx = useRef(0); const my = useRef(0)
  const rx = useRef(0); const ry = useRef(0)
  const raf = useRef(0)

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mx.current = e.clientX; my.current = e.clientY
      if (dotRef.current) { dotRef.current.style.left = `${e.clientX}px`; dotRef.current.style.top = `${e.clientY}px` }
    }
    const onOver = (e: MouseEvent) => {
      const big = (e.target as HTMLElement).matches('a,button,input,.c-field-tag,.c-plan')
      ringRef.current?.classList.toggle('big', big)
    }
    const tick = () => {
      rx.current += (mx.current - rx.current) * 0.12
      ry.current += (my.current - ry.current) * 0.12
      if (ringRef.current) { ringRef.current.style.left = `${rx.current}px`; ringRef.current.style.top = `${ry.current}px` }
      raf.current = requestAnimationFrame(tick)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseover', onOver)
    raf.current = requestAnimationFrame(tick)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseover', onOver)
      cancelAnimationFrame(raf.current)
    }
  }, [])

  return (
    <>
      <div ref={dotRef}  className="cosmic-cursor" />
      <div ref={ringRef} className="cosmic-cursor-ring" />
    </>
  )
}

// ── Star field canvas ─────────────────────────────────────────────────────────
function StarField() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    type Star = { x: number; y: number; size: number; alpha: number; speed: number; phase: number; color: string }
    let stars: Star[] = [], sW = 0, sH = 0, t = 0, raf = 0

    const init = () => {
      sW = canvas.width  = window.innerWidth
      sH = canvas.height = window.innerHeight
      const n = Math.floor((sW * sH) / 1800)
      stars = Array.from({ length: n }, () => {
        const r = Math.random()
        return { x: Math.random() * sW, y: Math.random() * sH, size: r < 0.7 ? 0.4 : r < 0.9 ? 0.8 : 1.2, alpha: Math.random() * 0.5 + 0.1, speed: Math.random() * 0.015 + 0.003, phase: Math.random() * Math.PI * 2, color: Math.random() > 0.85 ? '212,168,83' : '240,230,200' }
      })
    }
    const draw = () => {
      ctx.clearRect(0, 0, sW, sH)
      t += 0.008
      stars.forEach(s => {
        const a = s.alpha * (0.5 + 0.5 * Math.sin(t * s.speed * 40 + s.phase))
        ctx.beginPath(); ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${s.color},${a})`; ctx.fill()
      })
      const g = ctx.createRadialGradient(sW * 0.5, sH * 0.3, 0, sW * 0.5, sH * 0.3, sW * 0.4)
      g.addColorStop(0, 'rgba(212,168,83,0.012)'); g.addColorStop(1, 'transparent')
      ctx.fillStyle = g; ctx.fillRect(0, 0, sW, sH)
      raf = requestAnimationFrame(draw)
    }
    init(); draw()
    window.addEventListener('resize', init)
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', init) }
  }, [])

  return <canvas ref={canvasRef} className="cosmic-stars" />
}

// ── Timeline event ────────────────────────────────────────────────────────────
interface TEventData {
  side: 'left' | 'right'
  year: string; field: string; discovery: string; gap: string; delay: string
  lit?: boolean; active?: boolean
}

function TimelineEvent({ data, index }: { data: TEventData; index: number }) {
  const ref    = useRef<HTMLDivElement>(null)
  const dotRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      setTimeout(() => {
        setVisible(true)
        if (!data.lit) setTimeout(() => dotRef.current?.classList.add('lit'), 300)
      }, index * 180)
      obs.disconnect()
    }, { threshold: 0.12 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [index, data.lit])

  const card = (
    <div className={`c-t-card${data.active ? ' active' : ''}`}>
      <div className="c-t-field">{data.field}</div>
      <div className="c-t-discovery">{data.discovery}</div>
      <div className="c-t-gap-label">{data.gap}</div>
      <div className="c-t-delay"><span className="c-t-delay-dot" />{data.delay}</div>
    </div>
  )

  return (
    <div ref={ref} className={`c-t-event${visible ? ' show' : ''}`}>
      <div className="c-t-left">{data.side === 'left' && card}</div>
      <div className="c-t-center">
        <div ref={dotRef} className={`c-t-dot${data.lit ? ' lit' : ''}`} />
        <div className="c-t-year">{data.year}</div>
      </div>
      <div className="c-t-right">{data.side === 'right' && card}</div>
    </div>
  )
}

// ── Potential indicator canvas ─────────────────────────────────────────────────
function PotentialIndicatorCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const W = canvas.width, H = canvas.height, cx = W / 2, cy = H / 2
    let raf = 0

    const nodes = [
      { x: cx,        y: cy,        r: 10, label: 'Core',      bright: 1    },
      { x: cx - 120,  y: cy - 80,   r: 6,  label: 'Physics',   bright: 0.9  },
      { x: cx + 130,  y: cy - 70,   r: 7,  label: 'Cognition', bright: 0.95 },
      { x: cx + 140,  y: cy + 60,   r: 5,  label: 'Systems',   bright: 0.7  },
      { x: cx - 130,  y: cy + 75,   r: 6,  label: 'Language',  bright: 0.8  },
      { x: cx - 60,   y: cy - 140,  r: 4,  label: 'Maths',     bright: 0.75 },
      { x: cx + 70,   y: cy - 145,  r: 4,  label: 'History',   bright: 0.6  },
      { x: cx + 160,  y: cy - 10,   r: 4,  label: 'Biology',   bright: 0.65 },
      { x: cx - 165,  y: cy + 5,    r: 3,  label: 'Art',       bright: 0.5  },
      { x: cx,        y: cy + 155,  r: 5,  label: 'Economics', bright: 0.7  },
      { x: cx - 70,   y: cy + 145,  r: 3,  label: 'Ethics',    bright: 0.45 },
      { x: cx + 60,   y: cy + 140,  r: 4,  label: 'Design',    bright: 0.6  },
    ]
    const edges = [[0,1],[0,2],[0,3],[0,4],[1,5],[1,8],[2,6],[2,7],[3,11],[4,10],[5,6],[9,10],[9,11],[3,7],[4,8]]

    const draw = () => {
      ctx.clearRect(0, 0, W, H)
      const time = Date.now() / 2000
      edges.forEach(([a, b]) => {
        const na = nodes[a], nb = nodes[b]
        ctx.beginPath(); ctx.moveTo(na.x, na.y); ctx.lineTo(nb.x, nb.y)
        ctx.strokeStyle = `rgba(212,168,83,${0.08 + 0.04 * Math.sin(time + a)})`
        ctx.lineWidth = 0.8; ctx.stroke()
      })
      nodes.forEach((n, i) => {
        const pulse = 0.7 + 0.3 * Math.sin(time * 1.2 + i * 0.7)
        const gR = n.r * 5 * pulse
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, gR)
        g.addColorStop(0, `rgba(212,168,83,${0.12 * n.bright * pulse})`)
        g.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(n.x, n.y, gR, 0, Math.PI * 2)
        ctx.fillStyle = g; ctx.fill()

        ctx.beginPath(); ctx.arc(n.x, n.y, n.r * pulse * 0.8, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(212,168,83,${0.5 + 0.4 * n.bright * pulse})`
        ctx.shadowColor = 'rgba(212,168,83,.8)'; ctx.shadowBlur = 8; ctx.fill(); ctx.shadowBlur = 0

        if (n.r >= 5) {
          ctx.font = `300 ${Math.max(8, n.r + 3)}px 'Space Mono', monospace`
          ctx.fillStyle = `rgba(240,230,200,${0.25 * n.bright})`
          ctx.textAlign = 'center'
          ctx.fillText(n.label, n.x, n.y + n.r * 2 + 10)
        }
      })
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [])

  return <canvas ref={canvasRef} className="c-pi-canvas" width={500} height={360} />
}

// ── Scroll reveal hook ─────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function useReveal(): { ref: React.RefObject<any>; revealClass: string } {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ref = useRef<any>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current; if (!el) return
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { setVisible(true); obs.disconnect() }
    }, { threshold: 0.12 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return { ref, revealClass: visible ? 'c-reveal in' : 'c-reveal' }
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function HomeCosmic() {
  const [phase, setPhase]               = useState<Phase>({ kind: 'hero' })
  const [gateOpen, setGateOpen]         = useState(false)
  const [gateReason, setGateReason]     = useState<'mission' | 'limit'>('mission')
  const [sessionSparks, setSessionSparks] = useState<{ used: number; remaining: number } | null>(null)
  const [recentJourney, setRecentJourney] = useState<RecentJourney | null>(null)
  const [streakDays, setStreakDays]     = useState(0)
  const [fieldInput, setFieldInput]     = useState('')
  const [selectedField, setSelectedField] = useState('')
  const [showGapResult, setShowGapResult] = useState(false)
  const [gapBarWidth, setGapBarWidth]   = useState(0)

  const gapResultRef = useRef<HTMLDivElement>(null)
  const sessionId    = useMemo(getSessionId, [])
  const { user, getToken } = useAuth()
  const navigate = useNavigate()

  // Scroll-reveal refs
  const s2Intro   = useReveal()
  const s3Label   = useReveal()
  const s3Title   = useReveal()
  const s3Sub     = useReveal()
  const s3Input   = useReveal()
  const s3Tags    = useReveal()
  const s4Eye     = useReveal()
  const s4Title   = useReveal()
  const s4Body    = useReveal()
  const s4Plans   = useReveal()
  const s4Ctas    = useReveal()
  const s5Label   = useReveal()
  const s5Title   = useReveal()
  const s5Sub     = useReveal()
  const s5Caption = useReveal()

  // Add cosmic-mode class (cursor:none) + force dark nav while on this page
  useEffect(() => {
    const html = document.documentElement
    const hadDark = html.classList.contains('dark')
    html.classList.add('cosmic-mode', 'dark')
    return () => {
      html.classList.remove('cosmic-mode')
      if (!hadDark) html.classList.remove('dark')
    }
  }, [])

  // Restore spark count from server (handles page refresh)
  useEffect(() => {
    getSessionStatus(sessionId)
      .then(s => { if (s.sparks_used > 0) setSessionSparks({ used: s.sparks_used, remaining: s.sparks_remaining }) })
      .catch(() => {})
  }, [sessionId])

  // Recent journey + streak for signed-in users
  useEffect(() => {
    if (!user) { setRecentJourney(null); setStreakDays(0); return }
    getToken().then(token => {
      if (!token) return
      Promise.all([getPassport(token), getUserProfile(token)]).then(([passport, profile]) => {
        const inProgress = passport.journeys.filter(j => !j.fully_completed)
        setRecentJourney(inProgress[0] ?? null)
        setStreakDays(profile.streak_days ?? 0)
      }).catch(() => {})
    })
  }, [user, getToken])

  // Same spark handler as Home.tsx
  const handleSpark = useCallback(async (question: string) => {
    setPhase({ kind: 'loading', question })
    try {
      const token = await getToken()
      const res   = await askSpark({ question, session_id: sessionId }, token ?? undefined)
      setSessionSparks({ used: res.sparks_used, remaining: res.sparks_remaining })
      setPhase({ kind: 'sparked', question, answer: res.answer, mission: res.mission, sparksUsed: res.sparks_used, sparksRemaining: res.sparks_remaining })
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string }
      if (e.status === 429) { setGateReason('limit'); setGateOpen(true); setPhase({ kind: 'hero' }) }
      else { setPhase({ kind: 'error', question, message: e.message ?? 'Something went wrong.' }) }
    }
  }, [sessionId, getToken])

  // Show gap result instantly (static), then animate the bar
  const handleFieldSubmit = useCallback((field: string) => {
    const trimmed = field.trim(); if (!trimmed) return
    setSelectedField(trimmed)
    setFieldInput(trimmed)
    setShowGapResult(true)
    setGapBarWidth(0)
    setPhase({ kind: 'hero' })
    setTimeout(() => setGapBarWidth(28), 200)
    setTimeout(() => gapResultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 400)
  }, [])

  // "Close my gap" CTA: authed → explore, guest → spark flow
  const handleSparkCTA = useCallback((field: string) => {
    if (user) navigate(`/explore?q=${encodeURIComponent(field)}`)
    else handleSpark(field)
  }, [user, navigate, handleSpark])

  const fieldData      = selectedField ? FIELD_DATA[normaliseField(selectedField)] : null
  const currentMission = phase.kind === 'sparked' ? phase.mission : undefined
  const currentQuestion = phase.kind !== 'hero' ? phase.question : undefined

  const homeJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'ECALT',
    url: 'https://ecalt.vercel.app',
    description: 'AI-powered personalized learning journeys for curious minds of all ages.',
    potentialAction: { '@type': 'SearchAction', target: 'https://ecalt.vercel.app/journeys?q={search_term_string}', 'query-input': 'required name=search_term_string' },
  }

  return (
    <div className="cosmic-page">
      <PageMeta canonicalPath="/" jsonLd={homeJsonLd} />
      <Navigation />
      <CustomCursor />
      <StarField />
      <div className="cosmic-light-beam" />

      {/* ── CONTINUE CARD (signed-in users) ── */}
      {recentJourney && (
        <div className="c-continue-wrap">
          <button className="c-continue-btn" onClick={() => navigate(`/journey/${recentJourney.id}`)}>
            <span style={{ fontSize: '1.875rem', flexShrink: 0 }}>{recentJourney.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="c-continue-pretitle">Continue where you left off</div>
              <div className="c-continue-title">{recentJourney.title}</div>
              <div className="c-continue-bar-track">
                <div className="c-continue-bar-fill" style={{ width: `${Math.round((recentJourney.completed_steps / recentJourney.total_steps) * 100)}%` }} />
              </div>
            </div>
            <ArrowRight size={16} style={{ color: 'var(--gold)', flexShrink: 0 }} />
          </button>
          {streakDays > 1 && (
            <div className="c-streak">
              <Zap size={13} fill="#d97706" style={{ color: '#d97706' }} />
              {streakDays}-day streak
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════
          SECTION 1 — HERO
      ══════════════════════════════════ */}
      <section className="c-s1">
        <div className="c-brand-tag">ECALT &nbsp;·&nbsp; Everybody Can Learn Technology</div>
        <p className="c-star-fact">
          The light leaving <strong>Proxima Centauri</strong> right now will take{' '}
          <strong>4.2 years</strong> to reach Earth.<br />
          What you see in tonight's sky is already history.
        </p>
        <div className="c-s1-divider" />
        <div className="c-s1-main">
          <h1>Most of what you were taught<br />has <em>the same delay.</em></h1>
          <p>Knowledge exists long before it reaches most people. The gap between what humanity knows and what you know is not about intelligence. It is about transmission.</p>
        </div>
        <div className="c-scroll-cue">
          <span>See the delay</span>
          <div className="c-scroll-line" />
        </div>
      </section>

      {/* ══════════════════════════════════
          SECTION 2 — TIMELINE
      ══════════════════════════════════ */}
      <section className="c-s2">
        <div ref={s2Intro.ref} className={`c-s2-intro ${s2Intro.revealClass}`}>
          <div className="c-mono">The light delay in human knowledge</div>
          <h2>These ideas existed long before<br />they reached you.</h2>
          <p>The gap between discovery and common understanding.<br />Measured in decades. Sometimes in lifetimes.</p>
        </div>
        <div className="c-timeline-wrap">
          <div className="c-timeline-spine" />
          {TIMELINE_EVENTS.map((ev, i) => <TimelineEvent key={i} data={ev} index={i} />)}
        </div>
      </section>

      {/* ══════════════════════════════════
          SECTION 3 — PERSONAL GAP
      ══════════════════════════════════ */}
      <section className="c-s3">
        <div ref={s3Label.ref} className={`c-s3-label ${s3Label.revealClass}`}>
          Your Personal Light Delay
        </div>
        <h2 ref={s3Title.ref} className={`c-s3-title ${s3Title.revealClass}`}>
          What is the field<br />you think in <em>every day?</em>
        </h2>
        <p ref={s3Sub.ref} className={`c-s3-sub ${s3Sub.revealClass}`}>
          Type it below. We will show you the specific gap between where common understanding is and where the frontier actually sits.
        </p>

        <div ref={s3Input.ref} className={`c-field-input-wrap ${s3Input.revealClass}`}>
          <input
            className="c-field-input"
            type="text"
            placeholder="medicine, finance, engineering, design…"
            autoComplete="off"
            spellCheck={false}
            value={fieldInput}
            onChange={e => setFieldInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleFieldSubmit(fieldInput) }}
          />
          <div className="c-field-hint">press enter to see your gap</div>
        </div>

        <div ref={s3Tags.ref} className={`c-field-tags ${s3Tags.revealClass}`}>
          {FIELD_TAGS.map(tag => (
            <button
              key={tag}
              className={`c-field-tag${selectedField.toLowerCase() === tag.toLowerCase() ? ' active' : ''}`}
              onClick={() => handleFieldSubmit(tag)}
            >
              {tag}
            </button>
          ))}
        </div>

        {/* Gap result — shown after field is selected */}
        {showGapResult && fieldData && (
          <div ref={gapResultRef} className="c-gap-result">
            <div className="c-gap-visual">
              <div className="c-gap-label-you">Where most people are</div>
              <div className="c-gap-label-frontier">The frontier</div>
              <div className="c-gap-track" />
              <div className="c-gap-known" style={{ width: `${gapBarWidth}%` }} />
              <div className="c-gap-years">
                <span style={{ fontSize: '1.2rem', opacity: 0.5, fontFamily: "'Space Mono',monospace", fontStyle: 'normal' }}>
                  {fieldData.years}
                </span>
                &nbsp;<small>year gap</small>
              </div>
              <div className="c-gap-frontier"><div className="c-gap-frontier-dot" /></div>
            </div>

            <div className="c-result-insight">
              <div className="c-r-field">
                {selectedField.charAt(0).toUpperCase() + selectedField.slice(1)} · Frontier Insight
              </div>
              <div className="c-r-text">{fieldData.insight}</div>
              <div className="c-r-sub">{fieldData.sub}</div>
            </div>

            <p className="c-result-close">
              ECALT closes this gap — not with courses, but with the exact moment your life is ready to receive each insight.
            </p>

            {/* Spark states */}
            {phase.kind === 'loading' && (
              <div className="c-spark-loading">
                <Loader2 size={16} className="animate-spin" style={{ color: 'rgba(212,168,83,0.7)' }} />
                Sparking your curiosity…
              </div>
            )}

            {phase.kind === 'sparked' && (
              <div className="c-spark-answer">
                <div className="c-spark-answer-label">Your spark</div>
                <div className="c-spark-answer-text">{phase.answer}</div>
                <button
                  className="c-cta-primary"
                  style={{ marginTop: '1.25rem' }}
                  onClick={() => { setGateReason('mission'); setGateOpen(true) }}
                >
                  Start mission
                </button>
              </div>
            )}

            {phase.kind === 'error' && (
              <p style={{ color: 'rgba(212,168,83,0.6)', fontSize: '0.85rem', marginBottom: '1rem', textAlign: 'center' }}>
                {phase.message} —{' '}
                <button
                  onClick={() => handleSpark(selectedField)}
                  style={{ background: 'none', border: 'none', color: 'var(--gold2)', textDecoration: 'underline', fontSize: '0.85rem' }}
                >
                  try again
                </button>
              </p>
            )}

            {(phase.kind === 'hero') && (
              <div className="c-cta-row">
                <button className="c-cta-primary" onClick={() => handleSparkCTA(selectedField)}>
                  Close my gap
                </button>
                <button
                  className="c-cta-ghost"
                  onClick={() => document.getElementById('s5')?.scrollIntoView({ behavior: 'smooth' })}
                >
                  See my Potential Indicator
                </button>
              </div>
            )}

            {/* Spark meter for guests */}
            {!user && sessionSparks && (
              <p style={{ marginTop: '1rem', fontFamily: "'Space Mono',monospace", fontSize: '0.6rem', letterSpacing: '0.1em', color: 'rgba(212,168,83,0.4)', textAlign: 'center' }}>
                {sessionSparks.remaining} of 5 free sparks remaining
              </p>
            )}
          </div>
        )}
      </section>

      {/* ══════════════════════════════════
          SECTION 4 — PROMISE / PRICING
      ══════════════════════════════════ */}
      <section className="c-s4" id="s4">
        <div ref={s4Eye.ref} className={`c-promise-eyebrow ${s4Eye.revealClass}`}>
          Expansion Levels
        </div>
        <h2 ref={s4Title.ref} className={`c-promise-title ${s4Title.revealClass}`}>
          Choose how far<br />you want to <em>close the gap.</em>
        </h2>
        <p ref={s4Body.ref} className={`c-promise-body ${s4Body.revealClass}`}>
          Every plan includes your personal light delay measurement, an invisible learning path from exactly where you are to the frontier, and your Potential Indicator — the capability constellation that grows as your understanding does.
        </p>

        <div ref={s4Plans.ref} className={`c-plans ${s4Plans.revealClass}`}>
          {[
            { tier: 'Explorer',        name: 'Individual',   sub: 'per learner',    features: ['Unlimited questions', 'Personal light delay map', 'Invisible learning path', 'Potential Indicator', 'Image & document analysis'], featured: false },
            { tier: 'Family Universe', name: 'Family',       sub: 'up to 6 minds',  features: ['6 personal paths', '6 gap measurements', 'Family intelligence layer', '6 Potential Indicators', 'Parent insight dashboard'],   featured: true  },
            { tier: 'Institution',     name: 'Institution',  sub: 'cohort of 30',   features: ['30 personal paths', 'Cohort gap intelligence', 'Outcome reporting', 'Custom knowledge domains', 'API + LMS integration'],       featured: false },
          ].map(plan => (
            <div key={plan.tier} className={`c-plan${plan.featured ? ' featured' : ''}`}>
              <div className="c-plan-tier">{plan.tier}</div>
              <div className="c-plan-name">{plan.name}</div>
              <div className="c-plan-sub">{plan.sub}</div>
              {plan.features.map(f => <div key={f} className="c-plan-feat">{f}</div>)}
            </div>
          ))}
        </div>

        <div ref={s4Ctas.ref} className={`c-cta-row ${s4Ctas.revealClass}`}>
          <button className="c-cta-primary" onClick={() => navigate('/pricing')}>
            See pricing & plans
          </button>
          <button className="c-cta-ghost" onClick={() => handleSparkCTA('knowledge and learning')}>
            {user ? 'Start exploring' : '10 minutes free'}
          </button>
        </div>
      </section>

      {/* ══════════════════════════════════
          SECTION 5 — POTENTIAL INDICATOR
      ══════════════════════════════════ */}
      <section className="c-s5" id="s5">
        <div ref={s5Label.ref} className={`c-pi-label ${s5Label.revealClass}`}>
          Your Potential Indicator
        </div>
        <h2 ref={s5Title.ref} className={`c-pi-title ${s5Title.revealClass}`}>
          Not a certificate.<br />A map of your closing gap.
        </h2>
        <p ref={s5Sub.ref} className={`c-pi-sub ${s5Sub.revealClass}`}>
          Every insight you receive. Every connection you make. Every moment the delay closes. Rendered as a living constellation that is entirely, permanently yours.
        </p>
        <PotentialIndicatorCanvas />
        <p ref={s5Caption.ref} className={`c-pi-caption ${s5Caption.revealClass}`}>
          Each node is a capability you have demonstrated. Each edge is a connection your mind discovered. Yours grows every time you use ECALT.
        </p>
      </section>

      {/* ── FOOTER ── */}
      <footer className="c-footer">
        <div className="c-f-brand">ECALT © {new Date().getFullYear()}</div>
        <div className="c-f-links">
          <a href="#">Privacy</a>
          <a href="#">Terms</a>
          <a href="#">Legal</a>
          <a href="#">About</a>
          <a href="#">Contact</a>
        </div>
      </footer>

      <GateModal
        isOpen={gateOpen}
        reason={gateReason}
        mission={currentMission}
        question={currentQuestion}
        onClose={() => setGateOpen(false)}
      />
    </div>
  )
}
