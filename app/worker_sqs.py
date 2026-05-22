from __future__ import annotations

import asyncio
import json
import time

import boto3

from app.config import settings
from app.db import DynamoDBClient
from app.observability import Logger
from app.worker import Worker


async def poll_loop():
    log = Logger()
    log.info("worker.starting", queue_url=settings.sqs_queue_url)
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url
    sqs = boto3.client("sqs", **kwargs)
    db = DynamoDBClient()
    worker = Worker()
    while True:
        try:
            resp = sqs.receive_message(QueueUrl=settings.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=10)
            messages = resp.get("Messages", [])
            for msg in messages:
                body = json.loads(msg["Body"])
                load_id = body.get("load_id", "")
                if "load_data" in body and "event_type" not in body:
                    db.put_load({"load_id": body["load_id"], "customer_id": body["customer_id"], "state": body.get("initial_state", "on_route_to_delivery"), "version": 1, "load_data": body["load_data"], "session_state": {}})
                    sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
                    continue
                load_row = db.get_load(load_id)
                if not load_row:
                    log.error("worker.load_not_found", load_id=load_id)
                    sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
                    continue
                result = await worker.process_event(body, load_row)
                db.update_load(load_id=load_id, new_state=result["state"], session_state=result["session_state"], expected_version=load_row["version"])
                db.put_event({"load_id": load_id, "event_id": body.get("event_id", ""), "event_type": body.get("event_type", ""), "occurred_at": body.get("occurred_at", ""), "payload": body, "selected_branch": result["branch"]})
                if result["tool_calls"]:
                    db.put_tool_calls(result["tool_calls"])
                sqs.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])
        except Exception as e:
            log.error("worker.poll_error", error=str(e))
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(poll_loop())
