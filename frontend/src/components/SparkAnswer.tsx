interface SparkAnswerProps {
  question: string
  answer: string
}

export default function SparkAnswer({ question, answer }: SparkAnswerProps) {
  return (
    <div className="animate-in mb-6">
      <p className="text-xs text-slate-600 uppercase tracking-widest mb-2">You asked</p>
      <p className="text-slate-400 italic mb-5 text-sm">"{question}"</p>

      <div className="relative">
        {/* Glow behind */}
        <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-violet-600/30 to-cyan-500/20 blur-sm" />
        <div className="relative glass rounded-2xl p-6 border-l-2 border-violet-500/60">
          <p className="text-slate-100 leading-relaxed text-base">{answer}</p>
        </div>
      </div>
    </div>
  )
}
