import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, Sparkles, BookOpen, Zap, Star, ArrowRight } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import { useSubscription } from '../lib/SubscriptionContext'
import PageMeta from '../components/PageMeta'

// ── Floating particle ─────────────────────────────────────────────────────────
function Particle({ x, y, size, delay, duration }: { x: number; y: number; size: number; delay: number; duration: number }) {
  return (
    <span
      className="absolute rounded-full bg-violet-400 dark:bg-violet-500 opacity-0 pointer-events-none"
      style={{
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        animation: `floatUp ${duration}s ${delay}s ease-in infinite`,
      }}
    />
  )
}

const PARTICLES = Array.from({ length: 28 }, (_, i) => ({
  id: i,
  x: Math.random() * 100,
  y: 40 + Math.random() * 60,
  size: 3 + Math.random() * 5,
  delay: Math.random() * 4,
  duration: 3 + Math.random() * 4,
}))

// ── Feature row ───────────────────────────────────────────────────────────────
function Feature({ icon: Icon, label, delay }: { icon: React.ElementType; label: string; delay: number }) {
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(t)
  }, [delay])

  return (
    <div
      className={`flex items-center gap-3 transition-all duration-500 ${
        visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-4'
      }`}
    >
      <span className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-100 dark:bg-violet-900/40 flex items-center justify-center">
        <Icon className="w-4 h-4 text-violet-600 dark:text-violet-400" />
      </span>
      <span className="text-sm text-[var(--t2)]">{label}</span>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Welcome() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id') ?? ''

  const { user, getToken } = useAuth()
  const { plan, refresh } = useSubscription()

  const [planName, setPlanName] = useState<string | null>(null)
  const [synced, setSynced] = useState(false)
  const [checkVisible, setCheckVisible] = useState(false)
  const [headlineVisible, setHeadlineVisible] = useState(false)
  const didSync = useRef(false)

  // Sync subscription immediately on mount
  useEffect(() => {
    if (didSync.current || !user) return
    didSync.current = true

    const run = async () => {
      try {
        const token = await getToken()
        if (!token) return
        const res = await fetch('/api/v1/subscriptions/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ session_id: sessionId || null }),
        })
        if (res.ok) {
          const data = await res.json()
          setPlanName((data.plan?.name as string) ?? null)
          refresh()
        }
      } catch {
        // fallback to context plan name
      } finally {
        setSynced(true)
      }
    }
    run()
  }, [user, getToken, sessionId, refresh])

  // Use context plan name as fallback once context refreshes
  useEffect(() => {
    if (!planName && plan && plan.plan_id !== 'free_trial') {
      setPlanName(plan.name)
    }
  }, [plan, planName])

  // Staggered reveal animations
  useEffect(() => {
    const t1 = setTimeout(() => setCheckVisible(true), 300)
    const t2 = setTimeout(() => setHeadlineVisible(true), 700)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])

  const displayName = planName ?? (plan?.plan_id !== 'free_trial' ? plan?.name : null) ?? 'your plan'

  return (
    <>
      <PageMeta title="Welcome to ECALT" description="Your subscription is active." />

      <style>{`
        @keyframes floatUp {
          0%   { opacity: 0; transform: translateY(0) scale(0.5); }
          20%  { opacity: 0.7; }
          80%  { opacity: 0.5; }
          100% { opacity: 0; transform: translateY(-120px) scale(1.2); }
        }
        @keyframes pulseRing {
          0%   { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.8); opacity: 0; }
        }
        @keyframes checkPop {
          0%   { transform: scale(0.4); opacity: 0; }
          60%  { transform: scale(1.15); }
          100% { transform: scale(1); opacity: 1; }
        }
        .check-pop { animation: checkPop 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards; }
        .pulse-ring { animation: pulseRing 1.4s ease-out infinite; }
      `}</style>

      {/* Full-screen background */}
      <div className="relative min-h-screen bg-[var(--bg)] overflow-hidden flex flex-col items-center justify-center px-4">

        {/* Radial gradient glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-violet-500/10 dark:bg-violet-600/15 blur-3xl" />
        </div>

        {/* Floating particles */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          {PARTICLES.map(p => <Particle key={p.id} {...p} />)}
        </div>

        {/* Card */}
        <div className="relative z-10 w-full max-w-md glass-card rounded-3xl p-8 sm:p-10 flex flex-col items-center text-center gap-6">

          {/* Checkmark */}
          <div className="relative flex items-center justify-center">
            {checkVisible && (
              <>
                <span className="absolute w-24 h-24 rounded-full border-2 border-violet-400/50 pulse-ring" />
                <span className="absolute w-24 h-24 rounded-full border-2 border-violet-400/30 pulse-ring" style={{ animationDelay: '0.5s' }} />
              </>
            )}
            <span className={`w-20 h-20 rounded-full bg-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/30 ${checkVisible ? 'check-pop' : 'opacity-0'}`}>
              <CheckCircle2 className="w-10 h-10 text-white" strokeWidth={2} />
            </span>
          </div>

          {/* Headline */}
          <div className={`transition-all duration-700 ${headlineVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            <p className="text-xs font-semibold tracking-widest uppercase text-violet-500 dark:text-violet-400 mb-2">
              Payment confirmed
            </p>
            <h1 className="text-3xl sm:text-4xl font-bold text-[var(--t1)] leading-tight">
              Welcome to{' '}
              <span className="bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">
                ECALT
              </span>
            </h1>
            {synced && (
              <p className="mt-2 text-base text-[var(--t2)]">
                You're now on the{' '}
                <span className="font-semibold text-violet-600 dark:text-violet-400 capitalize">
                  {displayName}
                </span>{' '}
                plan.
              </p>
            )}
          </div>

          {/* Feature list */}
          {headlineVisible && (
            <div className="w-full flex flex-col gap-3 text-left">
              <Feature icon={Sparkles} label="Unlimited AI-powered conversations" delay={900} />
              <Feature icon={BookOpen} label="Your personal Knowledge Universe" delay={1100} />
              <Feature icon={Zap} label="Daily personalised curiosity sparks" delay={1300} />
              <Feature icon={Star} label="Mind Signature — know how you learn" delay={1500} />
            </div>
          )}

          {/* CTA */}
          <button
            onClick={() => navigate('/journeys', { replace: true })}
            className="btn-primary w-full flex items-center justify-center gap-2 mt-2 py-3.5 text-base"
          >
            Explore journeys
            <ArrowRight className="w-4 h-4" />
          </button>

          <p className="text-xs text-[var(--t3)]">
            A confirmation email is on its way to you.
          </p>
        </div>
      </div>
    </>
  )
}
