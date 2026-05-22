from __future__ import annotations

from typing import Any


TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": "Send an SMS message to the driver or dispatcher.",
            "parameters": {
                "type": "object",
                "required": ["recipient", "message"],
                "properties": {
                    "recipient": {"type": "string", "enum": ["driver", "dispatcher"]},
                    "message": {"type": "string", "description": "Short operational message text"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send or reply to an operational email.",
            "parameters": {
                "type": "object",
                "required": ["recipient", "subject", "body"],
                "properties": {
                    "recipient": {"type": "string", "enum": ["driver", "dispatcher", "carrier_team", "main_thread"]},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forward_email",
            "description": "Forward the current email and its attachments to the broker's special email address.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_slack_message",
            "description": "Send internal or broker-visible Slack-style notification.",
            "parameters": {
                "type": "object",
                "required": ["audience", "message"],
                "properties": {
                    "audience": {"type": "string", "enum": ["internal", "broker", "customer"]},
                    "message": {"type": "string"},
                    "escalation_type": {"type": "string", "description": "Optional escalation category"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_attachment",
            "description": "Classify one attachment by its ID.",
            "parameters": {
                "type": "object",
                "required": ["attachment_id"],
                "properties": {
                    "attachment_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_load_state",
            "description": "Update the load milestone state.",
            "parameters": {
                "type": "object",
                "required": ["target_state", "reason"],
                "properties": {
                    "target_state": {"type": "string", "enum": ["on_route_to_delivery", "at_delivery", "delivered", "pod_collected"]},
                    "reason": {"type": "string", "description": "Short reason for state change"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_eta",
            "description": "Store a driver-provided ETA.",
            "parameters": {
                "type": "object",
                "required": ["target_location", "eta_utc", "source"],
                "properties": {
                    "target_location": {"type": "string", "enum": ["delivery"]},
                    "eta_utc": {"type": "string", "description": "ISO 8601 UTC timestamp"},
                    "source": {"type": "string", "enum": ["driver", "dispatcher", "carrier", "system"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_timer",
            "description": "Schedule a follow-up timer.",
            "parameters": {
                "type": "object",
                "required": ["timer_type", "fire_at_utc", "reason"],
                "properties": {
                    "timer_type": {"type": "string", "enum": ["eta_followup", "pod_followup", "delivery_status_followup", "attachment_clarification"]},
                    "fire_at_utc": {"type": "string", "description": "ISO 8601 UTC timestamp when timer should fire"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_timers",
            "description": "Cancel timers for this load, optionally by type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timer_type": {"type": "string", "enum": ["eta_followup", "pod_followup", "delivery_status_followup", "attachment_clarification"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a non-urgent human follow-up task.",
            "parameters": {
                "type": "object",
                "required": ["title", "description", "task_type"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["missing_load_info", "pod_review", "lumper_review", "manual_followup", "other"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_issue",
            "description": "Create an urgent operational issue.",
            "parameters": {
                "type": "object",
                "required": ["title", "description", "issue_type"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "issue_type": {"type": "string", "enum": ["equipment_failure", "delivery_delay", "facility_problem", "other"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_load_info",
            "description": "Look up a specific field from the persisted load data.",
            "parameters": {
                "type": "object",
                "required": ["field"],
                "properties": {
                    "field": {"type": "string", "enum": ["delivery_address", "receiver_phone", "delivery_reference", "driver_contact"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_eta",
            "description": "Validate and normalize a driver-provided ETA string.",
            "parameters": {
                "type": "object",
                "required": ["raw_eta", "delivery_timezone"],
                "properties": {
                    "raw_eta": {"type": "string", "description": "The raw ETA text from the driver"},
                    "delivery_timezone": {"type": "string", "description": "IANA timezone string for the delivery stop"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_appointment_time",
            "description": "Return the appointment time for a stop.",
            "parameters": {
                "type": "object",
                "required": ["stop_type"],
                "properties": {
                    "stop_type": {"type": "string", "enum": ["pickup", "delivery"]},
                },
            },
        },
    },
]
