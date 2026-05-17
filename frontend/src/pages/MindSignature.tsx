import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Sparkles, Copy, Check, RefreshCw, ExternalLink } from 'lucide-react'
import { useAuth } from '../lib/AuthContext'
import PageMeta from '../components/PageMeta'
import ConstellationMap from '../components/constellation/ConstellationMap'

interface Domain {
  domain: string
  mastery_level: number
  concept_count: number
  learning_velocity: number
}

interface Signature {
  id: string
  display_name: string
  verification_hash: string
  capability_narrative: string
  domains: Domain[]
  constellation_data: { nodes: any[]; links: any[] }
  generated_at: string
}

export default function MindSignature() {
  const navigate = useNavigate()
  const { getToken } = useAuth()
  const [signature, setSignature] = useState<Signature | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSignature = async () => {
    try {
      const token = await getToken()
      if (!token) return
      const res = await fetch('/api/v1/mind-signature/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json()
      setSignature(data.signature ?? null)
    } catch {
      // non-critical
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSignature() }, [])

  const handleGenerate = async (force = false) => {
    setGenerating(true)
    setError(null)
    try {
      const token = await getToken()
      const endpoint = force ? '/api/v1/mind-signature/generate/force' : '/api/v1/mind-signature/generate'
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail ?? 'Could not generate signature.')
      } else {
        setSignature(data.signature)
      }
    } catch {
      setError('Something went wrong. Try again.')
    } finally {
      setGenerating(false)
    }
  }

  const copyHash = async () => {
    if (!signature) return
    await navigator.clipboard.writeText(signature.verification_hash)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const paragraphs = signature?.capability_narrative?.split('\n\n').filter(Boolean) ?? []

  return (
    <>
      <PageMeta title="Mind Signature" description="Your verified learning constellation." />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-10">
        <div className="max-w-4xl mx-auto">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 mb-8 transition-colors"
          >
            <ArrowLeft size={12} /> Back
          </button>

          <div className="flex items-center gap-3 mb-2">
            <Sparkles size={18} className="text-violet-500 dark:text-violet-400" />
            <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Mind Signature</h1>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-8">
            A verified constellation of your demonstrated intellectual range.
          </p>

          {loading ? (
            <div className="flex items-center justify-center py-24">
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : signature ? (
            <div className="space-y-6">
              {/* Constellation + domains */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card rounded-2xl p-6 flex items-center justify-center min-h-[280px]">
                  <ConstellationMap data={signature.constellation_data} />
                </div>

                <div className="glass-card rounded-2xl p-6 flex flex-col">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
                    Domain Mastery
                  </h2>
                  <div className="space-y-3 flex-1">
                    {signature.domains.map(d => (
                      <div key={d.domain}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-slate-700 dark:text-slate-300 capitalize">{d.domain}</span>
                          <span className="text-[10px] text-slate-500">{d.concept_count} concepts · {Math.round(d.mastery_level * 100)}%</span>
                        </div>
                        <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-violet-500 to-cyan-500 rounded-full transition-all duration-700"
                            style={{ width: `${Math.round(d.mastery_level * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Narrative */}
              <div className="glass-card rounded-2xl p-6">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
                  Capability Narrative
                </h2>
                <div className="space-y-4">
                  {paragraphs.map((p, i) => (
                    <p key={i} className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{p}</p>
                  ))}
                </div>
              </div>

              {/* Verification + actions */}
              <div className="glass-card rounded-2xl p-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                      Verification Hash
                    </p>
                    <p className="text-[11px] font-mono text-slate-600 dark:text-slate-400 break-all">
                      {signature.verification_hash}
                    </p>
                    <p className="text-[10px] text-slate-400 dark:text-slate-600 mt-1">
                      Generated {new Date(signature.generated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={copyHash}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-700/50 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                    >
                      {copied ? <Check size={12} /> : <Copy size={12} />}
                      {copied ? 'Copied' : 'Copy hash'}
                    </button>
                    <button
                      onClick={() => navigate(`/verify/${signature.verification_hash}`)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-100 dark:bg-violet-500/15 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-500/25 transition-all"
                    >
                      <ExternalLink size={12} />
                      View public page
                    </button>
                    <button
                      onClick={() => handleGenerate(true)}
                      disabled={generating}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all disabled:opacity-50"
                    >
                      <RefreshCw size={12} className={generating ? 'animate-spin' : ''} />
                      Refresh
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="glass-card rounded-2xl p-10 flex flex-col items-center text-center gap-5">
              <div className="w-16 h-16 rounded-2xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center">
                <Sparkles size={28} className="text-violet-500 dark:text-violet-400" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">
                  No Mind Signature yet
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">
                  Keep exploring. Once you've built depth across a few domains, your Mind Signature will emerge.
                </p>
              </div>
              {error && (
                <p className="text-xs text-rose-500 dark:text-rose-400">{error}</p>
              )}
              <div className="flex gap-3">
                <button
                  onClick={() => handleGenerate(false)}
                  disabled={generating}
                  className="px-5 py-2 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-60"
                >
                  {generating ? 'Generating…' : 'Generate signature'}
                </button>
                <button
                  onClick={() => navigate('/learn')}
                  className="px-5 py-2 rounded-xl text-sm font-semibold border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:border-violet-400 dark:hover:border-violet-500/50 transition-all"
                >
                  Keep learning
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
