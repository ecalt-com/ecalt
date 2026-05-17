import { useEffect, useState, useCallback } from 'react'
import { Network, Sparkles } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../lib/AuthContext'

interface KnowledgeNode {
  concept: string
  domain: string
  strength: number
}

const DOMAIN_COLORS: Record<string, string> = {
  biology:     'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  physics:     'bg-violet-500/20 text-violet-300 border-violet-500/30',
  chemistry:   'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  math:        'bg-amber-500/20 text-amber-300 border-amber-500/30',
  history:     'bg-orange-500/20 text-orange-300 border-orange-500/30',
  technology:  'bg-blue-500/20 text-blue-300 border-blue-500/30',
  psychology:  'bg-pink-500/20 text-pink-300 border-pink-500/30',
  philosophy:  'bg-purple-500/20 text-purple-300 border-purple-500/30',
  arts:        'bg-rose-500/20 text-rose-300 border-rose-500/30',
  language:    'bg-teal-500/20 text-teal-300 border-teal-500/30',
  economics:   'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  engineering: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  astronomy:   'bg-slate-500/20 text-slate-300 border-slate-500/30',
  medicine:    'bg-green-500/20 text-green-300 border-green-500/30',
}

function nodeSize(strength: number): string {
  if (strength >= 0.8) return 'text-sm'
  if (strength >= 0.55) return 'text-xs'
  return 'text-[11px]'
}

interface KnowledgeUniverseProps {
  refreshTrigger: number
}

export default function KnowledgeUniverse({ refreshTrigger }: KnowledgeUniverseProps) {
  const { getToken } = useAuth()
  const navigate = useNavigate()
  const [nodes, setNodes] = useState<KnowledgeNode[]>([])
  const [hasSignature, setHasSignature] = useState(false)

  const fetchNodes = useCallback(async () => {
    try {
      const token = await getToken()
      if (!token) return
      const [nodesRes, sigRes] = await Promise.all([
        fetch('/api/v1/knowledge/nodes', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/mind-signature/me', { headers: { Authorization: `Bearer ${token}` } }),
      ])
      if (nodesRes.ok) {
        const data = await nodesRes.json()
        setNodes(data.nodes ?? [])
      }
      if (sigRes.ok) {
        const data = await sigRes.json()
        setHasSignature(!!data.signature)
      }
    } catch {
      // non-critical
    }
  }, [getToken])

  useEffect(() => {
    fetchNodes()
  }, [fetchNodes, refreshTrigger])

  return (
    <div className="h-full flex flex-col p-4">
      <div className="flex items-center gap-2 mb-4">
        <Network size={14} className="text-cyan-400" />
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Knowledge universe
        </span>
      </div>

      {nodes.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xs text-slate-600 text-center leading-relaxed">
            Start a conversation to discover your knowledge universe
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="flex flex-wrap gap-1.5">
            {nodes.map((node) => {
              const colorClass = DOMAIN_COLORS[node.domain] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30'
              return (
                <span
                  key={node.concept}
                  title={`${node.domain} · strength ${Math.round(node.strength * 100)}%`}
                  className={`inline-flex items-center px-2 py-0.5 rounded-full border ${colorClass} ${nodeSize(node.strength)} font-medium transition-all duration-300`}
                >
                  {node.concept}
                </span>
              )
            })}
          </div>

          <div className="mt-4 flex items-center justify-between">
            {nodes.length >= 5 && (
              <p className="text-[10px] text-slate-500 dark:text-slate-600">
                {nodes.length} concept{nodes.length !== 1 ? 's' : ''} discovered
              </p>
            )}
            {hasSignature && (
              <button
                onClick={() => navigate('/mind-signature')}
                className="flex items-center gap-1 text-[10px] text-violet-500 dark:text-violet-400 hover:text-violet-600 dark:hover:text-violet-300 transition-colors ml-auto"
              >
                <Sparkles size={10} />
                View Mind Signature
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
