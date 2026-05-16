import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'ECALT — Turn Curiosity Into Capability',
  description:
    'AI-driven learning for kids and adults. Ask any question, get a personalized learning journey built just for you.',
  keywords: ['learning', 'AI', 'education', 'elearning', 'kids', 'adults', 'curiosity'],
  authors: [{ name: 'ECALT' }],
  openGraph: {
    title: 'ECALT — Turn Curiosity Into Capability',
    description: 'Ask anything. AI maps your learning journey.',
    type: 'website',
    siteName: 'ECALT',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ECALT — Turn Curiosity Into Capability',
    description: 'Ask anything. AI maps your learning journey.',
  },
}

export const viewport: Viewport = {
  themeColor: '#080b14',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-[#080b14] text-slate-100 antialiased font-[var(--font-inter)]">
        {children}
      </body>
    </html>
  )
}
