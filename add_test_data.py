#!/usr/bin/env python3
"""
Skripta za dodavanje test podataka u bazu
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models

def add_test_data():
    db = SessionLocal()

    try:
        # Dodajemo 6 rack-ova
        racks_data = [
            {"name": "Rack A1", "description": "Glavni rack u sali A", "serial_number": "RACK-A1-001", "total_units": 42, "max_power": 5000},
            {"name": "Rack A2", "description": "Backup rack u sali A", "serial_number": "RACK-A2-002", "total_units": 42, "max_power": 4500},
            {"name": "Rack B1", "description": "Glavni rack u sali B", "serial_number": "RACK-B1-003", "total_units": 48, "max_power": 6000},
            {"name": "Rack B2", "description": "Storage rack u sali B", "serial_number": "RACK-B2-004", "total_units": 24, "max_power": 3000},
            {"name": "Rack C1", "description": "Network rack u sali C", "serial_number": "RACK-C1-005", "total_units": 12, "max_power": 1500},
            {"name": "Rack C2", "description": "Test rack u sali C", "serial_number": "RACK-C2-006", "total_units": 18, "max_power": 2000},
        ]

        for rack_data in racks_data:
            rack = models.Rack(**rack_data)
            db.add(rack)

        # Dodajemo 8 uređaja
        devices_data = [
            {"name": "Dell PowerEdge R740", "description": "Web server", "serial_number": "DELL-R740-001", "units_occupied": 2, "power_consumption": 750},
            {"name": "HP ProLiant DL380", "description": "Database server", "serial_number": "HP-DL380-002", "units_occupied": 2, "power_consumption": 800},
            {"name": "Cisco Catalyst 2960", "description": "Network switch", "serial_number": "CISCO-2960-003", "units_occupied": 1, "power_consumption": 150},
            {"name": "NetApp FAS2750", "description": "Storage system", "serial_number": "NETAPP-FAS2750-004", "units_occupied": 4, "power_consumption": 1200},
            {"name": "Juniper EX4300", "description": "Core switch", "serial_number": "JUNIPER-EX4300-005", "units_occupied": 1, "power_consumption": 200},
            {"name": "IBM System x3650", "description": "Application server", "serial_number": "IBM-X3650-006", "units_occupied": 2, "power_consumption": 650},
            {"name": "APC Smart-UPS 3000", "description": "UPS system", "serial_number": "APC-SMART-007", "units_occupied": 3, "power_consumption": 300},
            {"name": "Checkpoint 7000", "description": "Firewall appliance", "serial_number": "CHKPT-7000-008", "units_occupied": 1, "power_consumption": 180},
        ]

        for device_data in devices_data:
            device = models.Device(**device_data)
            db.add(device)

        db.commit()
        print("✅ Dodano 6 rack-ova i 8 uređaja u bazu!")

        # Dodeljujemo neke uređaje rack-ovima
        assignments = [
            (1, 1),  # Dell server u Rack A1
            (2, 1),  # HP server u Rack A1
            (3, 5),  # Cisco switch u Rack C1
            (4, 4),  # NetApp storage u Rack B2
            (5, 5),  # Juniper switch u Rack C1
            (6, 2),  # IBM server u Rack A2
        ]

        for device_id, rack_id in assignments:
            device = db.query(models.Device).filter(models.Device.id == device_id).first()
            if device:
                device.rack_id = rack_id

        db.commit()
        print("✅ Dodeljeno 6 uređaja rack-ovima!")

    except Exception as e:
        print(f"❌ Greška: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_test_data()