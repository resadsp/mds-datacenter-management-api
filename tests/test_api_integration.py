import uuid
import asyncio

import httpx
import pytest

from app.main import app


async def _login_admin(client: httpx.AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin1", "password": "admin123"},
    )
    assert response.status_code == 200
    return response.json()


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def _create_rack(
    client: httpx.AsyncClient,
    headers: dict,
    *,
    total_units: int = 10,
    max_power: int = 1200,
) -> dict:
    rack_serial = f"RACK-T-{uuid.uuid4().hex[:10]}"
    rack_create = await client.post(
        "/api/v1/racks/",
        json={
            "name": "Rack Test",
            "description": "Integration rack",
            "serial_number": rack_serial,
            "total_units": total_units,
            "max_power": max_power,
        },
        headers=headers,
    )
    assert rack_create.status_code == 200
    return rack_create.json()


async def _create_device(
    client: httpx.AsyncClient,
    headers: dict,
    *,
    units_occupied: int = 1,
    power_consumption: int = 100,
) -> dict:
    device_serial = f"DEV-T-{uuid.uuid4().hex[:10]}"
    device_create = await client.post(
        "/api/v1/devices/",
        json={
            "name": "Device Test",
            "description": "Integration device",
            "serial_number": device_serial,
            "units_occupied": units_occupied,
            "power_consumption": power_consumption,
        },
        headers=headers,
    )
    assert device_create.status_code == 200
    return device_create.json()


@pytest.mark.asyncio
async def test_login_accepts_oauth_form_payload():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "grant_type": "password",
                "username": "admin1",
                "password": "admin123",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body


@pytest.mark.asyncio
async def test_oauth_token_endpoint_accepts_password_form():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin1",
                "password": "admin123",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body


@pytest.mark.asyncio
async def test_me_endpoint_accepts_access_token_query_param():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": "admin1",
                "password": "admin123",
            },
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]

        me_response = await client.get(f"/api/v1/auth/me?access_token={access_token}")
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "admin1"


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout_revocation_flow():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        old_refresh = login_payload["refresh_token"]

        refresh_response = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert refresh_response.status_code == 200
        rotated = refresh_response.json()
        new_refresh = rotated["refresh_token"]

        replay_old = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert replay_old.status_code == 401

        logout_response = await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
        assert logout_response.status_code == 200
        assert "message" in logout_response.json()

        refresh_after_logout = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
        assert refresh_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_devices_and_racks_pagination_envelope():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        rack_serial = f"RACK-T-{uuid.uuid4().hex[:10]}"
        device_serial = f"DEV-T-{uuid.uuid4().hex[:10]}"

        rack_create = await client.post(
            "/api/v1/racks/",
            json={
                "name": "Rack Test",
                "description": "Pagination test rack",
                "serial_number": rack_serial,
                "total_units": 10,
                "max_power": 1200,
            },
            headers=headers,
        )
        assert rack_create.status_code == 200
        rack_id = rack_create.json()["id"]

        device_create = await client.post(
            "/api/v1/devices/",
            json={
                "name": "Device Test",
                "description": "Pagination test device",
                "serial_number": device_serial,
                "units_occupied": 1,
                "power_consumption": 100,
            },
            headers=headers,
        )
        assert device_create.status_code == 200
        device_id = device_create.json()["id"]

        devices_page = await client.get(
            "/api/v1/devices/?page=1&page_size=1&sort_by=id&sort_order=asc",
            headers=headers,
        )
        assert devices_page.status_code == 200
        devices_payload = devices_page.json()
        assert "items" in devices_payload and "meta" in devices_payload
        assert isinstance(devices_payload["items"], list)
        assert devices_payload["meta"]["page"] == 1
        assert devices_payload["meta"]["page_size"] == 1

        racks_page = await client.get(
            "/api/v1/racks/?page=1&page_size=1&sort_by=id&sort_order=asc",
            headers=headers,
        )
        assert racks_page.status_code == 200
        racks_payload = racks_page.json()
        assert "items" in racks_payload and "meta" in racks_payload
        assert isinstance(racks_payload["items"], list)
        assert racks_payload["meta"]["page"] == 1
        assert racks_payload["meta"]["page_size"] == 1

        delete_device = await client.delete(f"/api/v1/devices/{device_id}", headers=headers)
        assert delete_device.status_code == 200

        delete_rack = await client.delete(f"/api/v1/racks/{rack_id}", headers=headers)
        assert delete_rack.status_code == 200


@pytest.mark.asyncio
async def test_assign_device_edge_cases_capacity_and_double_assign():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        tiny_units_rack = await _create_rack(client, headers, total_units=1, max_power=1000)
        tiny_power_rack = await _create_rack(client, headers, total_units=10, max_power=100)
        normal_rack = await _create_rack(client, headers, total_units=10, max_power=1500)

        big_units_device = await _create_device(client, headers, units_occupied=3, power_consumption=50)
        big_power_device = await _create_device(client, headers, units_occupied=1, power_consumption=300)
        normal_device = await _create_device(client, headers, units_occupied=1, power_consumption=100)

        units_fail = await client.post(
            f"/api/v1/devices/{big_units_device['id']}/assign/{tiny_units_rack['id']}",
            headers=headers,
        )
        assert units_fail.status_code == 400
        assert "jedinica" in units_fail.json()["detail"].lower()

        power_fail = await client.post(
            f"/api/v1/devices/{big_power_device['id']}/assign/{tiny_power_rack['id']}",
            headers=headers,
        )
        assert power_fail.status_code == 400
        assert "snage" in power_fail.json()["detail"].lower()

        first_assign = await client.post(
            f"/api/v1/devices/{normal_device['id']}/assign/{normal_rack['id']}",
            headers=headers,
        )
        assert first_assign.status_code == 200

        second_assign = await client.post(
            f"/api/v1/devices/{normal_device['id']}/assign/{tiny_units_rack['id']}",
            headers=headers,
        )
        assert second_assign.status_code == 400
        assert "već dodeljen" in second_assign.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_not_found_entities_and_rack_delete_with_assignment():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        rack = await _create_rack(client, headers, total_units=8, max_power=800)
        device = await _create_device(client, headers, units_occupied=1, power_consumption=100)

        missing_device = await client.post(f"/api/v1/devices/999999/assign/{rack['id']}", headers=headers)
        assert missing_device.status_code == 404

        missing_rack = await client.post(f"/api/v1/devices/{device['id']}/assign/999999", headers=headers)
        assert missing_rack.status_code == 404

        assign_ok = await client.post(f"/api/v1/devices/{device['id']}/assign/{rack['id']}", headers=headers)
        assert assign_ok.status_code == 200

        delete_rack_while_assigned = await client.delete(f"/api/v1/racks/{rack['id']}", headers=headers)
        assert delete_rack_while_assigned.status_code == 400
        assert "dodeljenim uređajima" in delete_rack_while_assigned.json()["detail"].lower()

        unassign = await client.post(f"/api/v1/devices/{device['id']}/unassign", headers=headers)
        assert unassign.status_code == 200

        delete_rack_after_unassign = await client.delete(f"/api/v1/racks/{rack['id']}", headers=headers)
        assert delete_rack_after_unassign.status_code == 200


@pytest.mark.asyncio
async def test_crud_conflict_edges_for_device_and_rack_updates():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        rack = await _create_rack(client, headers, total_units=6, max_power=900)
        device = await _create_device(client, headers, units_occupied=2, power_consumption=200)

        stale_device_update = await client.put(
            f"/api/v1/devices/{device['id']}",
            headers=headers,
            json={
                "name": "Device Updated",
                "description": "Stale update",
                "serial_number": device["serial_number"],
                "units_occupied": 2,
                "power_consumption": 210,
                "version": device["version"] + 5,
            },
        )
        assert stale_device_update.status_code == 409

        stale_rack_update = await client.put(
            f"/api/v1/racks/{rack['id']}",
            headers=headers,
            json={
                "name": "Rack Updated",
                "description": "Stale update",
                "serial_number": rack["serial_number"],
                "total_units": 6,
                "max_power": 900,
                "version": rack["version"] + 3,
            },
        )
        assert stale_rack_update.status_code == 409

        assign_ok = await client.post(f"/api/v1/devices/{device['id']}/assign/{rack['id']}", headers=headers)
        assert assign_ok.status_code == 200

        rack_state = await client.get(f"/api/v1/racks/{rack['id']}", headers=headers)
        assert rack_state.status_code == 200
        rack_payload = rack_state.json()

        invalid_capacity_update = await client.put(
            f"/api/v1/racks/{rack['id']}",
            headers=headers,
            json={
                "name": rack_payload["name"],
                "description": rack_payload.get("description"),
                "serial_number": rack_payload["serial_number"],
                "total_units": 1,
                "max_power": rack_payload["max_power"],
                "version": rack_payload["version"],
            },
        )
        assert invalid_capacity_update.status_code == 400
        assert "zauzetosti" in invalid_capacity_update.json()["detail"].lower()


@pytest.mark.asyncio
async def test_assign_idempotency_key_replay_returns_same_success():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        rack = await _create_rack(client, headers, total_units=8, max_power=800)
        device = await _create_device(client, headers, units_occupied=1, power_consumption=100)
        idem_key = f"idem-{uuid.uuid4().hex}"

        first_assign = await client.post(
            f"/api/v1/devices/{device['id']}/assign/{rack['id']}",
            headers={**headers, "Idempotency-Key": idem_key},
        )
        assert first_assign.status_code == 200

        replay_assign = await client.post(
            f"/api/v1/devices/{device['id']}/assign/{rack['id']}",
            headers={**headers, "Idempotency-Key": idem_key},
        )
        assert replay_assign.status_code == 200
        assert replay_assign.json().get("message") == "Uređaj dodeljen rack-u"


@pytest.mark.asyncio
async def test_concurrent_device_updates_create_single_winner_and_single_conflict():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])
        device = await _create_device(client, headers, units_occupied=1, power_consumption=120)

        shared_version = device["version"]

        async def do_update(new_name: str):
            return await client.put(
                f"/api/v1/devices/{device['id']}",
                headers=headers,
                json={
                    "name": new_name,
                    "description": "Concurrent update",
                    "serial_number": device["serial_number"],
                    "units_occupied": 1,
                    "power_consumption": 120,
                    "version": shared_version,
                },
            )

        first_response, second_response = await asyncio.gather(
            do_update("Concurrent-A"),
            do_update("Concurrent-B"),
        )

        status_codes = sorted([first_response.status_code, second_response.status_code])
        assert status_codes == [200, 409]


@pytest.mark.asyncio
async def test_restore_archived_device_and_rack_flow():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        login_payload = await _login_admin(client)
        headers = _auth_headers(login_payload["access_token"])

        rack = await _create_rack(client, headers, total_units=8, max_power=800)
        device = await _create_device(client, headers, units_occupied=1, power_consumption=100)

        assign_ok = await client.post(f"/api/v1/devices/{device['id']}/assign/{rack['id']}", headers=headers)
        assert assign_ok.status_code == 200

        delete_device = await client.delete(f"/api/v1/devices/{device['id']}", headers=headers)
        assert delete_device.status_code == 200

        restore_device = await client.post(f"/api/v1/devices/{device['id']}/restore", headers=headers)
        assert restore_device.status_code == 200

        device_detail = await client.get(f"/api/v1/devices/{device['id']}", headers=headers)
        assert device_detail.status_code == 200
        assert device_detail.json().get("deleted_at") is None

        unassign = await client.post(f"/api/v1/devices/{device['id']}/unassign", headers=headers)
        assert unassign.status_code == 200

        delete_rack = await client.delete(f"/api/v1/racks/{rack['id']}", headers=headers)
        assert delete_rack.status_code == 200

        restore_rack = await client.post(f"/api/v1/racks/{rack['id']}/restore", headers=headers)
        assert restore_rack.status_code == 200

        rack_detail = await client.get(f"/api/v1/racks/{rack['id']}", headers=headers)
        assert rack_detail.status_code == 200
        assert rack_detail.json().get("deleted_at") is None
