from fastapi import APIRouter, Depends

from app.core.auth import get_required_user
from app.services.knowledge_service import get_nodes_for_user
from app.services.spark_service import generate_daily_spark

router = APIRouter()


@router.get("/nodes")
async def get_knowledge_nodes(uid: str = Depends(get_required_user)):
    nodes = await get_nodes_for_user(uid)
    return {"nodes": nodes}


@router.get("/spark")
async def get_daily_spark(uid: str = Depends(get_required_user)):
    spark = await generate_daily_spark(uid)
    return {"spark": spark}
