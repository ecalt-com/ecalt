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

export type MarketplaceStatus = 'private' | 'pending_review' | 'published' | 'rejected'

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
  hero_image_url?: string | null
  created_at: string
  marketplace_status: MarketplaceStatus
  popularity_score: number
  like_count: number
  forked_from_id?: string | null
  is_owner: boolean
}

export type LearnerPurpose = 'research_paper' | 'professional_growth' | 'personal_curiosity' | 'teaching_others' | 'fun'
export type TopicExpertise = 'beginner' | 'intermediate' | 'advanced' | 'expert'

export interface ExploreRequest {
  question: string
  age_group?: AgeGroup
  level?: string
  learner_purpose?: LearnerPurpose
  topic_expertise?: TopicExpertise
  refinement_context?: string
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

// ── Visual Intelligence ──────────────────────────────────────────────────────
// Mirrors backend/app/models/visual_schemas.py / visual_recipe_schemas.py.
// See backend/plans/visual-intelligence/frontend-changes.md for the contract.

export type VisualStrategy =
  | 'NONE' | 'REUSE_VLO' | 'NATIVE_RENDER' | 'RETRIEVE_LICENSED_ASSET'
  | 'GENERATE_IMAGE' | 'GENERATE_VIDEO' | 'TEXT_ONLY'

export type VisualRendererType =
  | 'process_flow' | 'cycle' | 'cause_effect' | 'comparison' | 'timeline'
  | 'hierarchy' | 'part_to_whole' | 'before_after' | 'quantity_comparison' | 'progressive_sequence'

export interface StepVisualResponse {
  journey_id: string
  step_id: string
  status: 'pending' | 'unavailable' | 'ready'
  strategy?: VisualStrategy
  vlo_id?: string
  modality?: string
  renderer_type?: VisualRendererType
  recipe?: Record<string, unknown>
  pedagogical_role?: string
  // Set instead of renderer_type/recipe for retrieved/generated-image VLOs
  // (modality 'retrieved_image' | 'generated_image').
  asset_url?: string
  asset_type?: string
  attribution?: string
  license_type?: string
}

export interface VisualConnection { from: string; to: string }

export interface ProcessFlowRecipe {
  pattern: 'process_flow'
  title: string
  nodes: { id: string; label: string; role: 'input' | 'process' | 'output' }[]
  connections: VisualConnection[]
  progressiveReveal: boolean
}

export interface CycleRecipe {
  pattern: 'cycle'
  title: string
  nodes: { id: string; label: string }[]
  connections: VisualConnection[]
  progressiveReveal: boolean
  looping: boolean
}

export interface CauseEffectRecipe {
  pattern: 'cause_effect'
  title: string
  nodes: { id: string; label: string; role: 'cause' | 'mechanism' | 'effect' }[]
  connections: VisualConnection[]
}

export interface ComparisonRecipe {
  pattern: 'comparison'
  title: string
  columns: { id: string; label: string; items: string[] }[]
}

export interface TimelineRecipe {
  pattern: 'timeline'
  title: string
  events: { id: string; label: string; when: string }[]
  progressiveReveal: boolean
}

export interface HierarchyRecipe {
  pattern: 'hierarchy'
  title: string
  nodes: { id: string; label: string; parentId: string | null }[]
}

export interface PartToWholeRecipe {
  pattern: 'part_to_whole'
  title: string
  whole: string
  parts: { id: string; label: string; description?: string | null }[]
}

export interface BeforeAfterRecipe {
  pattern: 'before_after'
  title: string
  before: { label: string; description: string }
  after: { label: string; description: string }
}

export interface QuantityComparisonRecipe {
  pattern: 'quantity_comparison'
  title: string
  items: { id: string; label: string; value: number; unit?: string | null }[]
}

export interface ProgressiveSequenceRecipe {
  pattern: 'progressive_sequence'
  title: string
  steps: { id: string; label: string; content: string }[]
  autoPlay: boolean
}

export type VisualRecipe =
  | ProcessFlowRecipe | CycleRecipe | CauseEffectRecipe | ComparisonRecipe | TimelineRecipe
  | HierarchyRecipe | PartToWholeRecipe | BeforeAfterRecipe | QuantityComparisonRecipe | ProgressiveSequenceRecipe

export type VisualEventType =
  | 'visual_impression' | 'visual_started' | 'visual_completed'
  | 'visual_replayed' | 'visual_skipped' | 'visual_interaction' | 'visual_error'

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
