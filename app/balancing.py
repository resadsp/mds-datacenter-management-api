def balance_devices(devices, racks):
    """
    Algoritam za balansiranje uređaja po rack-ovima.

    Cilj: Rasporediti uređaje tako da se postigne što ravnomernija iskorišćenost
    maksimalne potrošnje energije po rack-ovima (0-100%).

    Algoritam:
    1. Sortira uređaje po potrošnji energije opadajuće (greedy pristup)
    2. Za svaki uređaj pronalazi najbolji rack sa najviše preostale snage
    3. Proverava da li uređaj staje (jedinice i snaga)
    4. Ako ne može nigde da stane, dodaje u nedodeljene

    Args:
        devices: Lista dict-ova sa 'units_occupied' i 'power_consumption'
        racks: Lista dict-ova sa 'total_units' i 'max_power'

    Returns:
        assignments: Lista tuple-a (device_index, rack_index)
        unassigned: Lista indeksa uređaja koji nisu dodeljeni
    """
    # Sortiramo uređaje po potrošnji opadajuće za bolje balansiranje
    device_indices = sorted(range(len(devices)), key=lambda i: devices[i]['power_consumption'], reverse=True)

    assignments = []  # Lista uspešnih dodela
    rack_usage = [{'units': 0, 'power': 0.0} for _ in racks]  # Trenutno stanje rack-ova
    unassigned = []  # Nedodeljeni uređaji

    # Prolazimo kroz svaki uređaj
    for idx in device_indices:
        device = devices[idx]
        best_rack = None
        best_remaining = -1  # Najbolja preostala snaga

        # Tražimo najbolji rack za ovaj uređaj
        for r_idx, rack in enumerate(racks):
            usage = rack_usage[r_idx]

            # Proveravamo da li uređaj staje u rack
            if (usage['units'] + device['units_occupied'] <= rack['total_units'] and
                usage['power'] + device['power_consumption'] <= rack['max_power']):

                # Računamo preostalu snagu
                remaining_power = rack['max_power'] - usage['power']

                # Biramo rack sa najviše preostale snage
                if remaining_power > best_remaining:
                    best_remaining = remaining_power
                    best_rack = r_idx

        # Ako smo našli odgovarajući rack, dodeljujemo
        if best_rack is not None:
            assignments.append((idx, best_rack))
            rack_usage[best_rack]['units'] += device['units_occupied']
            rack_usage[best_rack]['power'] += device['power_consumption']
        else:
            # Uređaj ne može da se smesti nigde
            unassigned.append(idx)

    return assignments, unassigned