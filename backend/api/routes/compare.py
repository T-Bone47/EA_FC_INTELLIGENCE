"""Comparison endpoint (§32): side-by-side + 'why A is better for THIS user'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import rate_limit_default, validate_game_version
from backend.api.schemas import CompareRequest
from backend.services.comparison_service import ComparisonService

router = APIRouter(prefix="/api", tags=["compare"],
                   dependencies=[Depends(rate_limit_default)])

_service = ComparisonService()


@router.post("/compare")
def compare(body: CompareRequest) -> dict:
    gv = validate_game_version(body.game_version)
    req = None
    if body.user_context is not None:
        if body.user_context.game_version.upper() != gv:
            raise HTTPException(422, "user_context.game_version must match "
                                     "the comparison game_version — never mixed")
        req = body.user_context.to_requirements()
    try:
        return _service.compare(gv, body.entity_ids, req)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
