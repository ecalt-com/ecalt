from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_acting_uid
from app.services.knowledge_service import get_nodes_for_user
from app.services.spark_service import generate_daily_spark
from app.services.subscription_service import check_budget, record_usage
from app.services.provider_service import get_config

router = APIRouter()


@router.get("/nodes")
async def get_knowledge_nodes(ctx: tuple = Depends(get_acting_uid)):
    uid, _ = ctx
    nodes = await get_nodes_for_user(uid)
    return {"nodes": nodes}


@router.get("/spark")
async def get_daily_spark(ctx: tuple = Depends(get_acting_uid)):
    uid, _ = ctx
    allowed, reason = check_budget(uid, context="ai")
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    spark, in_tok, out_tok = await generate_daily_spark(uid)
    if in_tok > 0:
        record_usage(uid, in_tok, out_tok, get_config("daily_spark")["model"],
                     interaction_type="daily_spark")
    return {"spark": spark}
