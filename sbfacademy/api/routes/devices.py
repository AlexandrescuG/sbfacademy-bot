from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sbfacademy.api.deps import current_user
from sbfacademy.core import db

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceBody(BaseModel):
    fcm_token: str
    platform: str = "android"


@router.post("")
async def register_device(body: DeviceBody, user: dict = Depends(current_user)):
    db.upsert_device(user["user_id"], body.fcm_token, body.platform)
    return {"ok": True}
