import type { StepVisualResponse } from '../../../lib/types'
import { VisualCard } from '../shared'

interface Props {
  stepVisual: StepVisualResponse
}

const VIDEO_TYPES = new Set(['mp4', 'webm'])

// Handles the two asset-backed strategies (RETRIEVE_LICENSED_ASSET,
// GENERATE_IMAGE) — these don't have a renderer_type/recipe, just a
// visual_assets row surfaced as asset_url/asset_type. No video assets exist
// yet (Phase 7 is deliberately unimplemented server-side), but the <video>
// branch costs nothing to have ready.
export default function ImageRenderer({ stepVisual }: Props) {
  if (!stepVisual.asset_url) return null
  const isVideo = stepVisual.asset_type ? VIDEO_TYPES.has(stepVisual.asset_type) : false
  const isGenerated = stepVisual.license_type === 'generated'

  return (
    <VisualCard>
      <div className="rounded-xl overflow-hidden bg-white">
        {isVideo ? (
          <video
            src={stepVisual.asset_url}
            controls
            playsInline
            className="w-full h-auto max-h-[420px] object-contain"
          />
        ) : (
          <img
            src={stepVisual.asset_url}
            alt="Illustration for this lesson"
            loading="lazy"
            className="w-full h-auto max-h-[420px] object-contain"
          />
        )}
      </div>
      {!isGenerated && stepVisual.attribution && (
        <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1.5">
          {stepVisual.attribution}
          {stepVisual.license_type ? ` · ${stepVisual.license_type}` : ''}
        </p>
      )}
    </VisualCard>
  )
}
