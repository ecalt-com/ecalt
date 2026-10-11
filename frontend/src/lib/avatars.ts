// Child profile avatars — stored server-side as a short key (users.avatar).
export const AVATARS: Record<string, { emoji: string; bg: string }> = {
  fox:     { emoji: '🦊', bg: 'bg-orange-100 dark:bg-orange-500/20' },
  owl:     { emoji: '🦉', bg: 'bg-amber-100 dark:bg-amber-500/20' },
  panda:   { emoji: '🐼', bg: 'bg-slate-100 dark:bg-slate-500/20' },
  octopus: { emoji: '🐙', bg: 'bg-pink-100 dark:bg-pink-500/20' },
  turtle:  { emoji: '🐢', bg: 'bg-emerald-100 dark:bg-emerald-500/20' },
  rocket:  { emoji: '🚀', bg: 'bg-sky-100 dark:bg-sky-500/20' },
  star:    { emoji: '⭐', bg: 'bg-yellow-100 dark:bg-yellow-500/20' },
  dino:    { emoji: '🦕', bg: 'bg-lime-100 dark:bg-lime-500/20' },
}

export const AVATAR_KEYS = Object.keys(AVATARS)

export function avatarFor(key: string | null | undefined) {
  return (key && AVATARS[key]) || null
}
