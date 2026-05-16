export type StepType = 'concept' | 'practice' | 'challenge' | 'explore'
export type AgeGroup = 'kids' | 'teens' | 'adults' | 'all'
export type Difficulty = 'beginner' | 'intermediate' | 'advanced'

export interface JourneyStep {
  id: string
  title: string
  description: string
  type: StepType
  estimated_minutes: number
  completed: boolean
  content?: string
}

export interface Journey {
  id: string
  question: string
  title: string
  description: string
  age_group: AgeGroup
  difficulty: Difficulty
  estimated_hours: number
  steps: JourneyStep[]
  tags: string[]
  icon: string
  created_at: string
}

export interface ExploreRequest {
  question: string
  age_group?: AgeGroup
  level?: string
}

export interface JourneysResponse {
  journeys: Journey[]
  total: number
}

// ── Spark (free tier) ─────────────────────────────────────────────────────────

export interface MissionStep {
  title: string
  type: StepType
  minutes: number
}

export interface Mission {
  id: string
  title: string
  tagline: string
  category: string
  difficulty: Difficulty
  estimated_minutes: number
  icon: string
  steps: MissionStep[]
}

export interface SparkRequest {
  question: string
  session_id: string
}

export interface SparkResponse {
  answer: string
  mission: Mission
  sparks_used: number
  sparks_remaining: number
}

// ── Passport ──────────────────────────────────────────────────────────────────

export interface CapabilityEntry {
  missionId: string
  missionTitle: string
  icon: string
  category: string
  completedAt: string
}
