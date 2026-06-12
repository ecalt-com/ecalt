import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ShieldCheck, ShieldX, ArrowLeft, Info } from 'lucide-react'
import PageMeta from '../components/PageMeta'
import ConstellationMap from '../components/constellation/ConstellationMap'
import { MindSignatureDisclaimer } from '../components/MindSignatureDisclaimer'

interface Domain {
  domain: string
  mastery_level: number
  concept_count: number
}

interface Signature {
  display_name: string
  verification_hash: string
  capability_narrative: string
  domains: Domain[]
  constellation_data: { nodes: any[]; links: any[] }
  generated_at: string
}

export default function Verify() {
  const { hash } = useParams<{ hash: string }>()
  const navigate = useNavigate()
  const [signature, setSignature] = useState<Signature | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    if (!hash) return
    fetch(`/api/v1/mind-signature/verify/${hash}`)
      .then(r => {
        if (r.status === 404) { setNotFound(true); return null }
        return r.json()
      })
      .then(data => {
        if (data) setSignature(data.signature)
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [hash])

  const paragraphs = signature?.capability_narrative?.split('\n\n').filter(Boolean) ?? []

  return (
    <>
      <PageMeta
        title={signature ? `${signature.display_name} — Mind Signature` : 'Verify Mind Signature'}
        description="Verified learning constellation by ECALT."
      />
      <div className="min-h-screen bg-[var(--bg-primary)] px-4 py-10">
        <div className="max-w-3xl mx-auto">
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300 mb-8 transition-colors"
          >
            <ArrowLeft size={12} /> ECALT
          </button>

          {loading ? (
            <div className="flex items-center justify-center py-24">
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : notFound ? (
            <div className="glass-card rounded-2xl p-6 sm:p-10 flex flex-col items-center text-center gap-4">
              <ShieldX size={32} className="text-rose-400" />
              <h1 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Signature not found</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                This hash doesn't match any record. It may have been revoked or the link is incorrect.
              </p>
            </div>
          ) : signature ? (
            <div className="space-y-6">
              {/* Legal disclaimer banner — must appear before signature content */}
              <div className="glass-card rounded-2xl p-5 flex items-start gap-3">
                <div className="w-8 h-8 rounded-xl bg-violet-100 dark:bg-violet-500/15 flex items-center justify-center shrink-0">
                  <Info size={16} className="text-violet-600 dark:text-violet-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-0.5">Verified Mind Signature</p>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                    This is an AI-generated capability indicator based on demonstrated learning engagement.
                    It is <strong>not</strong> an accredited educational credential, degree, or qualification.
                  </p>
                </div>
              </div>

              {/* Verified badge */}
              <div className="glass-card rounded-2xl p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-emerald-100 dark:bg-emerald-500/15 flex items-center justify-center shrink-0">
                  <ShieldCheck size={22} className="text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/15 px-2 py-0.5 rounded-full">
                      Verified by ECALT
                    </span>
                  </div>
                  <h1 className="text-lg font-bold text-slate-800 dark:text-slate-100">{signature.display_name}</h1>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Generated {new Date(signature.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                  </p>
                </div>
              </div>

              {/* Constellation + domains */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card rounded-2xl p-6 flex items-center justify-center min-h-[260px]">
                  <ConstellationMap data={signature.constellation_data} />
                </div>

                <div className="glass-card rounded-2xl p-6">
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-4">
                    Domain Mastery
                  </h2>
                  <div className="space-y-3">
                    {signature.domains.map(d => (
                      <div key={d.domain}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-slate-700 dark:text-slate-300 capitalize">{d.domain}</span>
                          <span className="text-xs text-slate-500">{d.concept_count} concepts · {Math.round(d.mastery_level * 100)}%</span>
                        </div>
                        <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-violet-500 to-cyan-500 rounded-full"
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
                <MindSignatureDisclaimer />
              </div>

              {/* Hash */}
              <div className="glass-card rounded-2xl p-4">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-600 mb-1">Verification Hash</p>
                <p className="text-xs font-mono text-slate-500 dark:text-slate-500 break-all">{signature.verification_hash}</p>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  )
}
