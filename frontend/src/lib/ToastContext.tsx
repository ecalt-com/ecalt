import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import clsx from 'clsx'

export type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: string
  message: string
  type: ToastType
}

interface ToastContextValue {
  addToast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue>({ addToast: () => {} })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, type: ToastType = 'success') => {
    const id = crypto.randomUUID()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3200)
  }, [])

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] flex flex-col gap-2 items-center pointer-events-none"
      >
        {toasts.map(t => (
          <div
            key={t.id}
            className={clsx(
              'px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg pointer-events-auto',
              'animate-toast-in whitespace-nowrap',
              t.type === 'success' && 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900',
              t.type === 'error'   && 'bg-rose-600 text-white',
              t.type === 'info'    && 'bg-violet-600 text-white',
            )}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
