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

export type LearnerPurpose = 'research_paper' | 'professional_growth' | 'personal_curiosity' | 'teaching_others' | 'fun'
export type TopicExpertise = 'beginner' | 'intermediate' | 'advanced' | 'expert'

export interface ExploreRequest {
  question: string
  age_group?: AgeGroup
  level?: string
  learner_purpose?: LearnerPurpose
  topic_expertise?: TopicExpertise
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

// ── Session ───────────────────────────────────────────────────────────────────

export interface SessionStatus {
  session_id: string
  sparks_used: number
  sparks_remaining: number
  limit: number
}

// ── Quiz ─────────────────────────────────────────────────────────────────────

export interface QuizQuestion {
  quiz_id: string
  concept: string
  difficulty: 'surface' | 'exploratory' | 'deep' | 'research'
  intro_phrase: string
  question: string
  hint_available: number
}

export interface QuizSet {
  quiz_set_id: string
  questions: QuizQuestion[]
  pass_threshold: number
}

export interface QuizHint {
  hint_num: number
  hint_text: string
  hints_remaining: number
}

export type QuizVerdict = 'excellent' | 'on_track' | 'off_track'

export interface QuizResult {
  verdict: QuizVerdict
  is_correct: boolean
  user_answer: string
  correct_answer: string
  explanation: string
  feedback: string
  missed: string | null
  hints_used: number
  concept: string
  difficulty: string
}

// ── Mind Signature ────────────────────────────────────────────────────────────

export interface CapabilityIndicators {
  conceptual_depth: number
  cross_domain_reach: number
  applied_reasoning: number
  emerging_frontiers: number
}

// ── Passport ──────────────────────────────────────────────────────────────────

export interface CapabilityEntry {
  missionId: string
  missionTitle: string
  icon: string
  category: string
  completedAt: string
}
