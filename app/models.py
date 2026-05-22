from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


CustomerID = Literal["customer_a", "customer_b", "customer_c"]
LoadState = Literal["on_route_to_delivery", "at_delivery", "delivered", "pod_collected"]
Channel = Literal["sms", "email"]
SenderType = Literal["driver", "dispatcher", "carrier", "broker", "shipper", "hero", "tool", "other"]


class Address(BaseModel):
    line_1: str
    line_2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Appointment(BaseModel):
    type: Literal["fixed", "window", "fcfs"]
    start_utc: str | None = None
    end_utc: str | None = None
    timezone: str


class Stop(BaseModel):
    stop_id: str
    type: Literal["pickup", "delivery"]
    status: str | None = None
    address: Address
    appointment: Appointment | dict[str, Any]
    coordinates: Coordinates | dict[str, Any]
    reference_numbers: dict[str, str | None] | None = None


class Company(BaseModel):
    name: str
    uuid: str | None = None


class PersonContact(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    uuid: str | None = None


class LoadData(BaseModel):
    external_load_id: str
    po_number: str | None = None
    instructions: str | None = None
    companies: dict[str, Company | dict[str, Any]]
    contacts: dict[str, PersonContact | dict[str, Any]] | None = None
    stops: list[Stop]


class Attachment(BaseModel):
    attachment_id: str
    file_name: str
    mime_type: str | None = None
    mock_classification: dict[str, Any]


class InboundCommunication(BaseModel):
    channel: Channel
    sender_type: SenderType
    sender_name: str | None = None
    content: str
    attachments: list[Attachment] = []


class TrackingPing(BaseModel):
    tracking_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    distance_to_delivery_miles: float = Field(ge=0)
    ping_sequence: int = Field(ge=1)
    provider: str | None = None


class LoadUpdate(BaseModel):
    milestone_state: LoadState | None = None
    load_data_patch: dict[str, Any] | None = None
    reason: str | None = None


# --- API Request Models ---

class LoadSeedRequest(BaseModel):
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    load_data: LoadData
    initial_state: LoadState | None = None


class SubmitTaskRequest(BaseModel):
    task_uuid: str = Field(min_length=1)
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    task_instruction_type: Literal["delivery_eta_checkpoint", "confirm_delivery"]
    requested_at: str
    source: Literal["api", "operator", "system"] | None = None
    payload: dict[str, Any] | None = None


class InboundCommunicationEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["inbound_communication"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    inbound_communication: InboundCommunication


class TrackingEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["tracking"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    tracking: TrackingPing


class LoadUpdateEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: Literal["load_update"]
    load_id: str = Field(min_length=1)
    customer_id: CustomerID
    occurred_at: str
    load_update: LoadUpdate


# --- Internal Records ---

class ToolCallRecord(BaseModel):
    tool_call_id: str
    event_id: str
    load_id: str
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    created_at: str
