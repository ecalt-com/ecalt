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

export interface ExploreResponse {
  journey: Journey
}

export interface JourneysResponse {
  journeys: Journey[]
  total: number
}
