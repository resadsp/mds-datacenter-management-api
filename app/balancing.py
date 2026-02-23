"""Algoritam balansiranja koji koristi endpoint /balance."""

import math

def balance_devices(devices, racks):
    """
    Predlaže raspored uređaja po rack-ovima sa ciljem ujednačene iskorišćenosti.

    Vraća:
        assignments: lista parova (device_index, rack_index)
        unassigned: lista indeksa uređaja koji nisu mogli biti dodeljeni
    """
    if not racks:
        return [], list(range(len(devices)))

    device_indices = sorted(
        range(len(devices)),
        key=lambda i: (devices[i]["power_consumption"], devices[i]["units_occupied"]),
        reverse=True,
    )

    assignments = []
    unassigned = []
    rack_usage = [{"units": 0, "power": 0.0} for _ in racks]

    total_max_power = sum(r["max_power"] for r in racks) or 1.0
    assigned_power = 0.0

    for d_idx in device_indices:
        d = devices[d_idx]
        best_rack = None
        best_score = float("inf")

        target_after = (assigned_power + d["power_consumption"]) / total_max_power

        for r_idx, rack in enumerate(racks):
            used = rack_usage[r_idx]

            fits_units = used["units"] + d["units_occupied"] <= rack["total_units"]
            fits_power = used["power"] + d["power_consumption"] <= rack["max_power"]
            if not (fits_units and fits_power):
                continue

            projected_utils = []
            for j, r in enumerate(racks):
                p = rack_usage[j]["power"]
                if j == r_idx:
                    p += d["power_consumption"]
                projected_utils.append(p / r["max_power"] if r["max_power"] > 0 else 1.0)

            # Score: što manja devijacija od cilja + manji spread među rack-ovima
            mean_u = sum(projected_utils) / len(projected_utils)
            std_u = math.sqrt(sum((u - mean_u) ** 2 for u in projected_utils) / len(projected_utils))
            spread = max(projected_utils) - min(projected_utils)
            target_dist = abs(projected_utils[r_idx] - target_after)

            score = (2.0 * target_dist) + (1.0 * std_u) + (0.5 * spread)

            if score < best_score:
                best_score = score
                best_rack = r_idx

        if best_rack is None:
            unassigned.append(d_idx)
            continue

        rack_usage[best_rack]["units"] += d["units_occupied"]
        rack_usage[best_rack]["power"] += d["power_consumption"]
        assigned_power += d["power_consumption"]
        assignments.append((d_idx, best_rack))

    return assignments, unassigned