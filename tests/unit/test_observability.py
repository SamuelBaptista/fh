import json
from app.observability import Logger, JsonlWriter


def test_logger_emits_json(capsys):
    log = Logger(load_id="load-1", event_id="evt-1")
    log.info("event.received", event_type="tracking")
    captured = capsys.readouterr()
    line = json.loads(captured.out.strip())
    assert line["load_id"] == "load-1"
    assert line["event_id"] == "evt-1"
    assert line["msg"] == "event.received"
    assert line["event_type"] == "tracking"
    assert "timestamp" in line


def test_jsonl_writer(tmp_path):
    writer = JsonlWriter(output_dir=tmp_path)
    writer.write("evt-1", {"tool": "send_sms", "result": "ok"})
    writer.write("evt-1", {"tool": "create_timer", "result": "ok"})

    path = tmp_path / "evt-1.jsonl"
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["tool"] == "send_sms"
