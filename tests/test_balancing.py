from app.balancing import balance_devices

# Test jednostavnog balansiranja - svi uređaji mogu da se smeste
def test_balance_simple():
    devices = [
        {'units_occupied': 1, 'power_consumption': 100},  # Mali uređaj
        {'units_occupied': 2, 'power_consumption': 200},  # Srednji uređaj
        {'units_occupied': 1, 'power_consumption': 150}   # Još jedan uređaj
    ]
    racks = [
        {'total_units': 4, 'max_power': 500},  # Veliki rack
        {'total_units': 3, 'max_power': 300}   # Srednji rack
    ]

    assignments, unassigned = balance_devices(devices, racks)

    # Svi uređaji treba da budu dodeljeni
    assert len(assignments) == 3
    assert len(unassigned) == 0

    # Proveravamo da su dodele validne
    assigned_racks = {}
    for dev_idx, rack_idx in assignments:
        assigned_racks[dev_idx] = rack_idx

    # Uređaj 1 (200W) ide u rack 0, uređaj 2 (150W) u rack 1, uređaj 0 (100W) u neki rack

# Test kada neki uređaj ne može da se smesti
def test_balance_unassigned():
    devices = [
        {'units_occupied': 5, 'power_consumption': 100}  # Preveliki uređaj
    ]
    racks = [
        {'total_units': 4, 'max_power': 500}  # Premali rack
    ]

    assignments, unassigned = balance_devices(devices, racks)

    # Nema dodela, uređaj je nedodeljen
    assert len(assignments) == 0
    assert unassigned == [0]

# Test ograničenja snage
def test_balance_power_limit():
    devices = [
        {'units_occupied': 1, 'power_consumption': 300},  # Veliki uređaj
        {'units_occupied': 1, 'power_consumption': 300}   # Još jedan veliki
    ]
    racks = [
        {'total_units': 2, 'max_power': 500}  # Dovoljno jedinica, ali ne snage za oba
    ]

    assignments, unassigned = balance_devices(devices, racks)

    # Samo jedan uređaj može da se smesti
    assert len(assignments) == 1
    assert len(unassigned) == 1

# Test sa više rack-ova
def test_balance_multiple_racks():
    devices = [
        {'units_occupied': 1, 'power_consumption': 100},
        {'units_occupied': 1, 'power_consumption': 100},
        {'units_occupied': 1, 'power_consumption': 100}
    ]
    racks = [
        {'total_units': 1, 'max_power': 200},  # Mali rack
        {'total_units': 2, 'max_power': 300}   # Veći rack
    ]

    assignments, unassigned = balance_devices(devices, racks)

    # Svi uređaji dodeljeni
    assert len(assignments) == 3
    assert len(unassigned) == 0