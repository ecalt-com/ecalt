from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_required_user
from app.services.mastery_service import should_generate_signature, update_domain_mastery
from app.services.mind_signature_service import (
    generate_mind_signature,
    get_latest_signature,
    get_signature_by_hash,
)

router = APIRouter()


@router.get("/me")
async def get_my_signature(uid: str = Depends(get_required_user)):
    sig = get_latest_signature(uid)
    if not sig:
        return {"signature": None}
    return {"signature": sig}


@router.post("/generate")
async def trigger_generate(uid: str = Depends(get_required_user)):
    update_domain_mastery(uid)
    if not should_generate_signature(uid):
        raise HTTPException(
            status_code=422,
            detail="Not enough domain mastery yet, or a signature was generated recently.",
        )
    sig = await generate_mind_signature(uid)
    return {"signature": sig}


@router.post("/generate/force")
async def force_generate(uid: str = Depends(get_required_user)):
    """Generate unconditionally — useful for manual refresh or testing."""
    update_domain_mastery(uid)
    sig = await generate_mind_signature(uid)
    return {"signature": sig}


@router.get("/verify/{verification_hash}")
async def verify_signature(verification_hash: str):
    """Public — no auth required."""
    sig = get_signature_by_hash(verification_hash)
    if not sig:
        raise HTTPException(status_code=404, detail="Signature not found")
    return {"verified": True, "signature": sig}
