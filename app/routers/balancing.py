"""Endpoint za predlog rasporeda uređaja po rack-ovima."""

from fastapi import APIRouter, Depends
from app.schemas import BalancingRequest, BalancingResponse, Assignment, ErrorResponse
from app.balancing import balance_devices
from app import models
from app.auth import require_roles

router = APIRouter()

# Endpoint za balansiranje uređaja po rack-ovima
@router.post(
    "/balance/",
    response_model=BalancingResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
def balance_devices_endpoint(
    request: BalancingRequest,
    _: models.User = Depends(require_roles("operator", "admin")),
):
    """Računa i vraća predložene dodele i nedodeljene uređaje."""
    devices = [d.model_dump() for d in request.devices]
    racks = [r.model_dump() for r in request.racks]

    assignments, unassigned = balance_devices(devices, racks)
    assignments = [Assignment(device_id=dev_idx, rack_id=rack_idx) for dev_idx, rack_idx in assignments]

    return BalancingResponse(assignments=assignments, unassigned_devices=unassigned)