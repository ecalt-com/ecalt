import clsx from 'clsx'
import { avatarFor } from '../../lib/avatars'

interface Props {
  name: string | null
  avatar?: string | null
  photoUrl?: string | null
  size?: 'sm' | 'lg'
}

// Child profiles show their chosen animal; the parent shows their Google
// photo, falling back to initials.
export default function ProfileAvatar({ name, avatar, photoUrl, size = 'sm' }: Props) {
  const box = size === 'lg' ? 'w-20 h-20 rounded-3xl text-4xl' : 'w-7 h-7 rounded-full text-sm'
  const a = avatarFor(avatar)
  if (a) {
    return <div className={clsx(box, a.bg, 'flex items-center justify-center')} aria-hidden="true">{a.emoji}</div>
  }
  if (photoUrl) {
    return <img src={photoUrl} alt="" className={clsx(box, 'object-cover')} referrerPolicy="no-referrer" />
  }
  const initials = (name ?? 'U').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div className={clsx(box, 'bg-violet-600 flex items-center justify-center text-white font-bold', size === 'lg' ? 'text-2xl' : 'text-xs')}>
      {initials}
    </div>
  )
}
