import type { ElementType } from 'react'
import { Zap, Users, GraduationCap, Building2 } from 'lucide-react'

export const PLAN_ICONS: Record<string, ElementType> = {
  free_trial: Zap, individual: Zap, student: GraduationCap,
  family: Users, university: Building2, enterprise: Building2,
}

export const PLAN_FEATURES: Record<string, string[]> = {
  free_trial: ['6 lifetime messages', 'Knowledge Universe preview', "Today's spark"],
  individual: ['Unlimited conversations', 'Knowledge Universe', 'Daily personalized spark', 'Image analysis', 'Mind Signature'],
  student: ['Same as Individual', 'Verified .edu discount', 'Study-focused sparks'],
  family: ['Up to 5 learners', 'Shared budget', 'Individual Knowledge Universes', 'Parent dashboard'],
  university: ['100+ seats', 'Admin dashboard', 'Usage analytics', 'LMS integration (roadmap)'],
  enterprise: ['Custom seat count', 'Custom model routing', 'SLA & priority support', 'Custom integrations'],
}

export const INTERACTION_LABELS: Record<string, string> = {
  daily_chat:           'Daily Chat',
  nudge:                'Nudge',
  onboarding:           'Onboarding',
  fingerprint:          'Fingerprint',
  mind_signature:       'Mind Signature',
  journey:              'Journey',
  step_content:         'Step Content',
  spark:                'Spark',
  daily_spark:          'Daily Spark',
  knowledge_extraction: 'Knowledge',
  quiz:                 'Quiz',
  unknown:              'Other',
}

export const FEATURE_COLORS = ['bg-violet-500', 'bg-emerald-500', 'bg-amber-400', 'bg-sky-500']
export const OTHER_COLOR = 'bg-slate-400'

export const TABS = [
  { id: 'overview',                label: 'Overview' },
  { id: 'plans',                   label: 'Pricing Plans' },
  { id: 'ai',                      label: 'AI Providers' },
  { id: 'prompts',                 label: 'AI Prompts' },
  { id: 'notification-templates',  label: 'Notif Templates' },
  { id: 'users',                   label: 'Users' },
  { id: 'coupons',                 label: 'Coupons' },
  { id: 'revenue',                 label: 'Revenue' },
  { id: 'retention',               label: 'Retention' },
  { id: 'funnel',                  label: 'Funnel' },
  { id: 'content',                 label: 'Content' },
  { id: 'impersonation-log',       label: 'Impersonation Log' },
] as const

export type TabId = typeof TABS[number]['id']

export const inputCls = 'mt-1 w-full bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-200 dark:border-slate-700 focus:border-violet-400 dark:focus:border-violet-500/50'
export const selectCls = 'bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs px-2 py-1.5 rounded-lg outline-none border border-slate-200 dark:border-slate-700 focus:border-violet-400 dark:focus:border-violet-500/50'
