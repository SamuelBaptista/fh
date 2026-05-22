from __future__ import annotations

import asyncio
import json
import os

from app.db import DynamoDBClient
from app.observability import Logger
from app.worker import Worker


_worker: Worker | None = None
_db: DynamoDBClient | None = None


def get_worker() -> Worker:
    global _worker
    if _worker is None:
        _worker = Worker()
    return _worker


def get_db() -> DynamoDBClient:
    global _db
    if _db is None:
        _db = DynamoDBClient()
    return _db


def handler(event, context):
    if os.environ.get("HANDLER") == "worker":
        return worker_handler(event, context)
    from mangum import Mangum
    from app.api import app
    mangum_handler = Mangum(app, lifespan="off")
    return mangum_handler(event, context)


def worker_handler(event, context):
    log = Logger()
    db = get_db()
    worker = get_worker()
    records = event.get("Records", [])
    for record in records:
        body = json.loads(record["body"])
        load_id = body.get("load_id", "")
        event_id = body.get("event_id", "")
        log.info("sqs.message_received", load_id=load_id, event_id=event_id)
        load_row = db.get_load(load_id)
        if not load_row:
            log.error("worker.load_not_found", load_id=load_id)
            continue
        result = asyncio.get_event_loop().run_until_complete(worker.process_event(body, load_row))
        db.update_load(load_id=load_id, new_state=result["state"], session_state=result["session_state"], expected_version=load_row["version"])
        db.put_event({"load_id": load_id, "event_id": event_id, "event_type": body.get("event_type", ""), "occurred_at": body.get("occurred_at", ""), "payload": body, "selected_branch": result["branch"]})
        if result["tool_calls"]:
            db.put_tool_calls(result["tool_calls"])
    return {"statusCode": 200}
