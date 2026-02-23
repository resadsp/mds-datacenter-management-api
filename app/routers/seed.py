"""Seed endpoint i pomoćna funkcija za unos demo/test podataka."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.database import SessionLocal
from app import models

router = APIRouter(prefix="/seed", tags=["Seed"])


def seed_data():
    """Popunjava bazu rack-ovima, uređajima i početnim dodelama (jednokratno)."""
    db = SessionLocal()
    try:
        if db.query(models.Rack).first():
            return {
                "ok": False,
                "status_code": status.HTTP_409_CONFLICT,
                "message": "Database already seeded.",
            }

        # ----------------------
        # SEED RACKS
        # ----------------------
        racks_data = [
            {"name":"Rack A1","description":"Glavni rack u sali A","serial_number":"RACK-A1-001","total_units":42,"max_power":5000},
            {"name":"Rack A2","description":"Backup rack u sali A","serial_number":"RACK-A2-002","total_units":42,"max_power":4500},
            {"name":"Rack B1","description":"Glavni rack u sali B","serial_number":"RACK-B1-003","total_units":48,"max_power":6000},
            {"name":"Rack B2","description":"Storage rack u sali B","serial_number":"RACK-B2-004","total_units":24,"max_power":3000},
            {"name":"Rack C1","description":"Network rack u sali C","serial_number":"RACK-C1-005","total_units":12,"max_power":1500},
            {"name":"Rack C2","description":"Test rack u sali C","serial_number":"RACK-C2-006","total_units":18,"max_power":2000},
            {"name":"Rack D1","description":"Compute rack u sali D","serial_number":"RACK-D1-007","total_units":42,"max_power":5500},
            {"name":"Rack D2","description":"Backup rack u sali D","serial_number":"RACK-D2-008","total_units":42,"max_power":4800},
            {"name":"Rack E1","description":"High density rack","serial_number":"RACK-E1-009","total_units":48,"max_power":7000},
            {"name":"Rack F1","description":"Security rack","serial_number":"RACK-F1-010","total_units":24,"max_power":2500},
            {"name":"Rack G1","description":"Test environment rack","serial_number":"RACK-G1-011","total_units":18,"max_power":2000},
        ]
        racks = [models.Rack(**r) for r in racks_data]
        db.add_all(racks)
        db.commit()

        # ----------------------
        # SEED DEVICES
        # ----------------------
        devices_data = [
            {"name":"Dell PowerEdge R740","description":"Web server","serial_number":"DELL-R740-001","units_occupied":2,"power_consumption":750},
            {"name":"HP ProLiant DL380","description":"Database server","serial_number":"HP-DL380-002","units_occupied":2,"power_consumption":800},
            {"name":"Cisco Catalyst 2960","description":"Network switch","serial_number":"CISCO-2960-003","units_occupied":1,"power_consumption":150},
            {"name":"NetApp FAS2750","description":"Storage system","serial_number":"NETAPP-FAS2750-004","units_occupied":4,"power_consumption":1200},
            {"name":"Juniper EX4300","description":"Core switch","serial_number":"JUNIPER-EX4300-005","units_occupied":1,"power_consumption":200},
            {"name":"IBM System x3650","description":"Application server","serial_number":"IBM-X3650-006","units_occupied":2,"power_consumption":650},
            {"name":"APC Smart-UPS 3000","description":"UPS system","serial_number":"APC-SMART-007","units_occupied":3,"power_consumption":300},
            {"name":"Checkpoint 7000","description":"Firewall appliance","serial_number":"CHKPT-7000-008","units_occupied":1,"power_consumption":180},
            {"name":"Dell PowerEdge R750","description":"Virtualization server","serial_number":"DELL-R750-009","units_occupied":2,"power_consumption":900},
            {"name":"HP ProLiant DL360","description":"Backup server","serial_number":"HP-DL360-010","units_occupied":1,"power_consumption":600},
            {"name":"Cisco Nexus 9000","description":"Core switch","serial_number":"CISCO-N9K-011","units_occupied":2,"power_consumption":400},
            {"name":"Fortinet FortiGate 100F","description":"Firewall appliance","serial_number":"FORTI-100F-012","units_occupied":1,"power_consumption":150},
            {"name":"Synology RackStation RS4021","description":"NAS storage","serial_number":"SYNO-RS4021-013","units_occupied":2,"power_consumption":350},
            {"name":"Supermicro SYS-1029","description":"Compute node","serial_number":"SM-1029-014","units_occupied":1,"power_consumption":500},
        ]
        devices = [models.Device(**d) for d in devices_data]
        db.add_all(devices)
        db.commit()

        # ----------------------
        # ASSIGN DEVICES → RACKS
        # ----------------------
        assignments = [
            (0, 0), (1, 0), (2, 4), (3, 3), (4, 4), (5, 1), (6, 9),
            (7, 9), (8, 6), (9, 1), (10, 4), (11, 9), (12, 3), (13, 6),
        ]
        for device_idx, rack_idx in assignments:
            devices[device_idx].rack_id = racks[rack_idx].id
        db.commit()

        return {
            "ok": True,
            "status_code": status.HTTP_200_OK,
            "message": "Database seeded successfully.",
        }
    except Exception as e:
        db.rollback()
        return {
            "ok": False,
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": f"Seed error: {e}",
        }
    finally:
        db.close()


@router.post("", summary="Seed baze kompletnim test podacima")
def run_seed():
    """HTTP endpoint omotač oko pomoćne funkcije seed_data."""
    result = seed_data()
    return JSONResponse(
        status_code=result["status_code"],
        content={"message": result["message"]},
    )