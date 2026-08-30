import { useEffect, useRef } from 'react'
import type { ComponentType } from 'react'
import type { StepVisualResponse, VisualRecipe, VisualRendererType } from '../../lib/types'
import { emitVisualEvent } from './telemetry'

import ProcessFlowRenderer from './renderers/ProcessFlowRenderer'
import CycleRenderer from './renderers/CycleRenderer'
import CauseEffectRenderer from './renderers/CauseEffectRenderer'
import ComparisonRenderer from './renderers/ComparisonRenderer'
import TimelineRenderer from './renderers/TimelineRenderer'
import HierarchyRenderer from './renderers/HierarchyRenderer'
import PartToWholeRenderer from './renderers/PartToWholeRenderer'
import BeforeAfterRenderer from './renderers/BeforeAfterRenderer'
import QuantityComparisonRenderer from './renderers/QuantityComparisonRenderer'
import ProgressiveSequenceRenderer from './renderers/ProgressiveSequenceRenderer'
import ImageRenderer from './renderers/ImageRenderer'

// Keyed by backend renderer_type (spec section 25). Deliberately a plain
// object, not a switch — adding a pattern later is a one-line registration,
// and an unregistered type (forward-compat with a server-side pattern this
// build hasn't shipped a renderer for yet) falls through to "render nothing"
// below rather than throwing.
const registry: Partial<Record<VisualRendererType, ComponentType<{ recipe: any; onInteraction?: any; onComplete?: any }>>> = {
  process_flow: ProcessFlowRenderer,
  cycle: CycleRenderer,
  cause_effect: CauseEffectRenderer,
  comparison: ComparisonRenderer,
  timeline: TimelineRenderer,
  hierarchy: HierarchyRenderer,
  part_to_whole: PartToWholeRenderer,
  before_after: BeforeAfterRenderer,
  quantity_comparison: QuantityComparisonRenderer,
  progressive_sequence: ProgressiveSequenceRenderer,
}

interface Props {
  journeyId: string
  stepId: string
  stepVisual: StepVisualResponse
  getToken: () => Promise<string | null>
}

// Never executes anything from `recipe` as code/HTML — it's typed data only
// (labels, ids, roles), rendered as text content by the registered
// components above. No dangerouslySetInnerHTML anywhere in this pipeline,
// unlike the mermaid/SVG diagram path in StepDiagram.tsx.
//
// Two shapes of "ready" (see backend visual_orchestrator_service):
//  - native pattern:  renderer_type + recipe set        -> pattern registry
//  - retrieved/generated image: asset_url set instead   -> ImageRenderer
export default function VisualLearningObject({ journeyId, stepId, stepVisual, getToken }: Props) {
  const impressionSent = useRef(false)
  const vloId = stepVisual.vlo_id
  const isNativePattern = !!stepVisual.renderer_type && !!stepVisual.recipe
  const isAsset = !!stepVisual.asset_url
  const ready = stepVisual.status === 'ready' && !!vloId && (isNativePattern || isAsset)

  useEffect(() => {
    if (!ready || impressionSent.current || !vloId) return
    impressionSent.current = true
    emitVisualEvent(journeyId, stepId, vloId, 'visual_impression', getToken, {
      renderer_type: stepVisual.renderer_type ?? stepVisual.modality,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, vloId])

  if (!ready || !vloId) return null

  if (isAsset) return <ImageRenderer stepVisual={stepVisual} />

  const Renderer = registry[stepVisual.renderer_type!]
  if (!Renderer) return null // forward-compat: unknown pattern, render nothing

  const onInteraction = (data: Record<string, unknown>) =>
    emitVisualEvent(journeyId, stepId, vloId, 'visual_interaction', getToken, data)
  const onComplete = () =>
    emitVisualEvent(journeyId, stepId, vloId, 'visual_completed', getToken, {})

  return <Renderer recipe={stepVisual.recipe as unknown as VisualRecipe} onInteraction={onInteraction} onComplete={onComplete} />
}
