import pytest
from fastapi.testclient import TestClient

from backend.app import app, appointments


@pytest.fixture(autouse=True)
def clear_storage():
    appointments.clear()
    yield
    appointments.clear()


client = TestClient(app)
PAYLOAD = {"patient_id": "patient-1", "provider_id": "provider-1", "scheduled_at": "2030-01-01T10:00:00Z"}


def test_create_get_delete():
    response = client.post("/appointments", json=PAYLOAD)
    assert response.status_code == 201
    appointment = response.json()
    assert appointment["status"] == "scheduled"
    assert client.get(f"/appointments/{appointment['id']}").json() == appointment
    assert client.delete(f"/appointments/{appointment['id']}").status_code == 204
    assert client.get(f"/appointments/{appointment['id']}").status_code == 404


def test_duplicate_provider_time_rejected():
    assert client.post("/appointments", json=PAYLOAD).status_code == 201
    assert client.post("/appointments", json={**PAYLOAD, "patient_id": "patient-2"}).status_code == 409


def test_equivalent_timezone_is_duplicate():
    client.post("/appointments", json=PAYLOAD)
    response = client.post("/appointments", json={**PAYLOAD, "scheduled_at": "2030-01-01T18:00:00+08:00"})
    assert response.status_code == 409


def test_other_provider_allowed():
    client.post("/appointments", json=PAYLOAD)
    assert client.post("/appointments", json={**PAYLOAD, "provider_id": "provider-2"}).status_code == 201


def test_deleted_slot_can_be_rebooked():
    appointment_id = client.post("/appointments", json=PAYLOAD).json()["id"]
    client.delete(f"/appointments/{appointment_id}")
    assert client.post("/appointments", json=PAYLOAD).status_code == 201


@pytest.mark.parametrize("change", [{"patient_id": ""}, {"scheduled_at": "invalid"},
                                     {"scheduled_at": "2030-01-01T10:00:00"}])
def test_invalid_input(change):
    assert client.post("/appointments", json={**PAYLOAD, **change}).status_code == 422


def test_delete_missing():
    assert client.delete("/appointments/missing").status_code == 404
