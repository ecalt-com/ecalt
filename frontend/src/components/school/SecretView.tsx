import clsx from 'clsx'
import { PICTURE_ICONS } from '../../lib/pictureIcons'
import type { SecretKind, StudentSecret } from '../../lib/schoolApi'

// Shows a student's picture password (icons + names) or PIN. Used where a
// secret is revealed once (new student, reset) and on printed login cards.
export default function SecretView({ kind, secret, size = 'md' }: {
  kind: SecretKind
  secret: StudentSecret
  size?: 'sm' | 'md'
}) {
  if (kind === 'picture' && Array.isArray(secret)) {
    const box = size === 'sm' ? 'w-10 h-10' : 'w-14 h-14'
    const icon = size === 'sm' ? 22 : 30
    return (
      <ol className="flex items-start gap-2" aria-label={`Picture password: ${secret.map(i => PICTURE_ICONS[i]?.name).join(', ')}`}>
        {secret.map((index, pos) => {
          const pic = PICTURE_ICONS[index]
          return (
            <li key={pos} className="flex flex-col items-center gap-1">
              <span className={clsx(box, 'rounded-xl bg-white border border-slate-200 flex items-center justify-center print:border-slate-400')}>
                {pic && <pic.Icon size={icon} className={pic.color} aria-hidden="true" />}
              </span>
              <span className="text-[10px] text-slate-500">{pos + 1}. {pic?.name}</span>
            </li>
          )
        })}
      </ol>
    )
  }
  return (
    <span className={clsx('font-mono font-bold tracking-[0.3em] text-slate-900 dark:text-slate-100 print:text-black', size === 'sm' ? 'text-lg' : 'text-2xl')}>
      {String(secret)}
    </span>
  )
}
