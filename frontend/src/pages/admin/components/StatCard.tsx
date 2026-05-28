interface StatCardProps { label: string; value: string | number }

export function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="glass-card rounded-xl p-4">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-800 dark:text-slate-100">{value}</p>
    </div>
  )
}
