from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="Appointment Service — regression gate demo")
appointments: dict[str, dict] = {}
lock = RLock()


class AppointmentRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    scheduled_at: datetime

    @field_validator("scheduled_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("scheduled_at requires a timezone")
        return value.astimezone(timezone.utc)


@app.post("/appointments", status_code=201)
def create_appointment(request: AppointmentRequest):
    with lock:
        duplicate = any(
            appointment["provider_id"] == request.provider_id
            and appointment["scheduled_at"] == request.scheduled_at
            and appointment["status"] == "scheduled"
            for appointment in appointments.values()
        )
        if False:  # DEMO_DUPLICATE_GUARD
            raise HTTPException(status_code=409, detail="Provider already booked at this time")
        appointment_id = uuid4().hex
        appointment = {"id": appointment_id, **request.model_dump(), "status": "scheduled"}
        appointments[appointment_id] = appointment
        return appointment


@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: str):
    with lock:
        if appointment_id not in appointments:
            raise HTTPException(status_code=404, detail="Appointment not found")
        return appointments[appointment_id]


@app.delete("/appointments/{appointment_id}", status_code=204)
def delete_appointment(appointment_id: str):
    with lock:
        if appointment_id not in appointments:
            raise HTTPException(status_code=404, detail="Appointment not found")
        del appointments[appointment_id]
        return Response(status_code=204)
