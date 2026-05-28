export interface PlanRow {
  plan_id: string
  name: string
  base_price_cents: number
  base_price_inr_paise: number | null
  token_budget_cents: number
  lifetime_message_limit: number | null
  max_seats: number
  is_active: boolean
  stripe_price_id: string | null
  razorpay_plan_id: string | null
}

export interface NewPlanForm {
  plan_id: string
  name: string
  base_price_cents: string
  base_price_inr_paise: string
  token_budget_cents: string
  max_seats: string
}

export interface Stats {
  total_users: number
  dau: number
  messages_today: number
  monthly_api_cost_cents: number
}

export interface UserRow {
  uid: string
  email: string | null
  display_name: string | null
  is_admin: boolean
  plan_id: string
  sub_status: string
  created_at: string
  budget_cents: number
  spent_cents: number
  input_tokens: number
  output_tokens: number
  cached_input_tokens: number
  message_count: number
  pct_used: number
}

export interface UserDetail {
  profile: {
    uid: string
    email: string | null
    display_name: string | null
    photo_url: string | null
    is_admin: boolean
    streak_days: number
    last_active_date: string | null
    age_group_flag: string | null
    account_status: string
    created_at: string
    plan_id: string
    plan_name: string
    sub_status: string
    payment_gateway: string | null
    current_period_start: string | null
    current_period_end: string | null
    budget_cents: number
    lifetime_message_limit: number | null
  }
  current_month: {
    spent_cents: number
    budget_cents: number | null
    pct_used: number
    input_tokens: number
    output_tokens: number
    cached_input_tokens: number
    message_count: number
  }
  lifetime: {
    lifetime_cost_cents: number
    lifetime_input_tokens: number
    lifetime_output_tokens: number
    lifetime_message_count: number
    lifetime_chat_messages: number
    total_conversations: number
    first_active_month: string | null
  }
  breakdown: {
    interaction_type: string
    input_tokens: number
    output_tokens: number
    cached_input_tokens: number
    estimated_cost_cents: number
    request_count: number
  }[]
  history: {
    period_start: string
    input_tokens: number
    output_tokens: number
    cached_input_tokens: number
    estimated_cost_cents: number
    message_count: number
  }[]
  coupons: {
    code: string
    description: string
    credit_applied_cents: number
    bonus_messages_applied: number
    redeemed_at: string
    credit_expires_at: string | null
    is_active: boolean
  }[]
}

export interface RevenueData {
  plan_distribution: {
    plan_id: string
    plan_name: string
    price_cents: number
    base_price_inr_paise: number | null
    user_count: number
    mrr_usd_cents: number
    mrr_inr_paise: number
  }[]
  status_breakdown: {
    status: string
    user_count: number
  }[]
  gateway_split: {
    payment_gateway: string
    subscriptions: number
    total_usd_cents: number
    total_inr_paise: number
  }[]
  summary: {
    total_mrr_usd_cents: number
    total_mrr_inr_paise: number
    total_paid_users: number
    total_trial_users: number
    total_free_users: number
    arpu_usd_cents: number
  }
}

export interface AIConfig {
  interaction_type: string
  provider: string
  model: string
}

export interface ModelOption {
  id: string
  label: string
}

export interface UsageByModel {
  model_used: string
  message_count: number
  total_cost_cents: number
}

export interface DailyUsage {
  day: string
  messages: number
}

export interface PlanMargin {
  plan_id: string
  plan_name: string
  price_cents: number
  budget_cents: number
  active_users: number
  total_spent_cents: number
  avg_spent_cents: number
  max_spent_cents: number
  cost_revenue_pct: number
}

export interface AtRiskUser {
  uid: string
  email: string | null
  display_name: string | null
  plan_id: string
  budget_cents: number
  spent_cents: number
  pct_used: number
}

export interface ByInteractionRow {
  interaction_type: string
  user_count: number
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  total_cost_cents: number
  avg_cost_per_user_cents: number
}

export interface CacheTrendPoint {
  period_start: string
  total_input: number
  total_cached: number
  cache_hit_pct: number
  total_cost_cents: number
}

export interface CostAnalysis {
  plan_margins: PlanMargin[]
  at_risk_users: AtRiskUser[]
  by_interaction: ByInteractionRow[]
  cache_trend: CacheTrendPoint[]
}

export interface TopJourney {
  id: string
  title: string
  icon: string | null
  difficulty: string | null
  estimated_hours: number | null
  age_group: string | null
  unique_learners: number
  total_step_completions: number
  total_steps: number
  fully_completed_users: number
  completion_pct: number
}

export interface ContentData {
  top_journeys: TopJourney[]
  completion_summary: {
    journeys_started: number
    users_with_progress: number
    avg_completion_pct: number
  }
  top_conversations: {
    id: string
    title: string | null
    uid: string
    email: string | null
    display_name: string | null
    message_count: number
    last_message_at: string | null
  }[]
  knowledge_growth: {
    day: string
    new_concepts: number
    unique_users: number
  }[]
}

export interface StepDropoff {
  step_id: string
  completions: number
}

export interface FunnelData {
  conversion: {
    total_signups_180d: number
    converted_30d: number; converted_30d_pct: number
    converted_60d: number; converted_60d_pct: number
    converted_90d: number; converted_90d_pct: number
    avg_days_to_convert: number | null
  }
  monthly_churn: {
    month: string
    cancellations: number
    new_subscriptions: number
  }[]
  trial_exhausted_never_upgraded: {
    uid: string
    email: string | null
    display_name: string | null
    signup_date: string | null
    lifetime_messages: number
  }[]
}

export interface FeatureUsageSummary {
  interaction_type: string
  unique_users: number
  total_requests: number
  total_input_tokens: number
  total_output_tokens: number
  total_cached_tokens: number
  total_cost_cents: number
  avg_cost_per_request_cents: number
}

export interface FeatureTrendPoint {
  period_start: string
  interaction_type: string
  total_requests: number
  total_cost_cents: number
}

export interface FeatureUsageData {
  this_month: FeatureUsageSummary[]
  trend: FeatureTrendPoint[]
  models: { model_used: string; message_count: number; total_cost_cents: number }[]
}

export interface RetentionData {
  active_users: { dau: number; wau: number; mau: number; stickiness: number }
  retention: {
    cohort_size: number
    cohort_window: string
    d1_count: number; d1_pct: number
    d7_count: number; d7_pct: number
    d30_count: number; d30_pct: number
  }
  weekly_signups: { week_start: string; new_users: number }[]
  inactive_users: {
    uid: string
    email: string | null
    display_name: string | null
    signup_date: string | null
    plan_id: string
    ai_requests_ever: number
    last_active_date: string | null
  }[]
}

export interface CouponRow {
  code: string
  description: string
  credit_cents: number
  bonus_messages: number
  plan_override: string | null
  duration_days: number | null
  max_redemptions: number | null
  redemption_count: number
  expires_at: string | null
  is_active: boolean
  created_at: string
  tag: string | null
}

export interface RedemptionRow {
  id: string
  uid: string
  display_name: string | null
  email: string | null
  credit_applied_cents: number
  bonus_messages_applied: number
  redeemed_at: string
  credit_expires_at: string | null
}

export interface CouponStats {
  active_coupons: number
  total_coupons: number
  total_redemptions: number
  total_credit_applied_cents: number
  unique_redeemers: number
}

export interface PromptRow {
  interaction_type:        string
  style_prompt:            string | null
  style_prompt_is_default: boolean
  default_style_prompt:    string
  output_contract_hint:    string
  style_prompt_updated_at: string | null
  style_prompt_updated_by: string | null
  provider:                string
  model:                   string
}

export interface PromptHistoryEntry {
  id:               number
  interaction_type: string
  old_style_prompt: string | null
  new_style_prompt: string
  changed_by:       string
  changed_at:       string
  reset_to_default: boolean
}

export interface NotificationTemplateRow {
  notification_type: string
  template:          string
  updated_at:        string | null
  updated_by:        string | null
}
