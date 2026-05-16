import { Component, ReactNode } from 'react'
import { Zap } from 'lucide-react'

interface State { error: Error | null }

export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-white dark:bg-[#080b14] flex items-center justify-center p-6">
          <div className="text-center max-w-sm">
            <div className="w-12 h-12 rounded-2xl bg-rose-100 dark:bg-rose-900/30 flex items-center justify-center mx-auto mb-4">
              <Zap size={22} className="text-rose-500" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">Something went wrong</h2>
            <p className="text-sm text-slate-500 mb-6">This page hit an unexpected error. Refreshing usually fixes it.</p>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold transition-colors"
            >
              Refresh page
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
