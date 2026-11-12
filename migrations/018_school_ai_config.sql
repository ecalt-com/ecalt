-- SC-401 / #18: admin-editable AI config rows for the school interaction types.
-- Seeds the current code defaults (provider_service.DEFAULT_CONFIG). style_prompt
-- stays NULL so the code's grounded prompts keep applying until an admin edits one.
-- Never overwrites a row an admin already changed.
INSERT INTO public.ai_provider_config (interaction_type, provider, model, style_prompt)
VALUES
  ('school_course_outline',      'openai', 'gpt-4.1',      NULL),
  ('school_step_content',        'openai', 'gpt-4.1-mini', NULL),
  ('school_faithfulness_critic', 'openai', 'gpt-4.1-mini', NULL)
ON CONFLICT (interaction_type) DO NOTHING;
