from fastapi import APIRouter
from app.schemas import BalancingRequest, BalancingResponse, Assignment
from app.balancing import balance_devices

router = APIRouter()

# Endpoint za balansiranje uređaja po rack-ovima
@router.post("/balance/", response_model=BalancingResponse)
def balance_devices_endpoint(request: BalancingRequest):
    # Pretvaramo Pydantic modele u dict-ove za algoritam
    devices = [d.dict() for d in request.devices]
    racks = [r.dict() for r in request.racks]

    # Pozivamo algoritam balansiranja
    assignments, unassigned = balance_devices(devices, racks)

    # Pretvaramo rezultate u Pydantic modele
    assignments = [Assignment(device_id=dev_idx, rack_id=rack_idx) for dev_idx, rack_idx in assignments]

    return BalancingResponse(assignments=assignments, unassigned_devices=unassigned)