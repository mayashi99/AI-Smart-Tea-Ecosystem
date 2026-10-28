"""Local append-only SHA-256 linked ledger for Component 04 tea batch passports."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


LEDGER_PATH = Path(__file__).resolve().parents[3] / "data" / "component04" / "passport_ledger.jsonl"
GENESIS = "0" * 64
_LOCK = Lock()


def _canonical(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_events() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    return [json.loads(line) for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _seal(body: dict, previous_hash: str) -> dict:
    entry = {**body, "previous_hash": previous_hash}
    entry["record_hash"] = hashlib.sha256(_canonical(entry)).hexdigest()
    return entry


def list_passports() -> dict:
    events = _read_events()
    batches: dict[str, dict] = {}
    for event in events:
        batch_id = event["batch_id"]
        passport = batches.setdefault(batch_id, {"batch_id": batch_id, "created_at": event["timestamp"], "events": []})
        passport["events"].append(event)
        passport["latest_event"] = event["event_type"]
        passport["latest_location"] = event.get("location")
        passport["updated_at"] = event["timestamp"]
    return {"passports": list(batches.values()), "ledger_valid": verify_ledger()["valid"], "ledger_records": len(events)}


def add_passport_event(
    batch_id: str,
    event_type: str,
    location: str,
    tea_grade: str,
    quantity_kg: float,
    note: str | None,
    quality_result: str | None = None,
    evidence_reference: str | None = None,
    actor_user_id: int | None = None,
) -> dict:
    with _LOCK:
        events = _read_events()
        previous_hash = events[-1]["record_hash"] if events else GENESIS
        body = {"batch_id": batch_id, "event_type": event_type, "location": location,
                "tea_grade": tea_grade, "quantity_kg": quantity_kg,
                "note": note, "quality_result": quality_result,
                "evidence_reference": evidence_reference, "actor_user_id": actor_user_id,
                "timestamp": datetime.now(timezone.utc).isoformat()}
        entry = _seal(body, previous_hash)
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER_PATH.open("a", encoding="utf-8", newline="\n") as ledger:
            ledger.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        return entry


def verify_ledger() -> dict:
    events = _read_events()
    previous_hash = GENESIS
    for index, event in enumerate(events, start=1):
        supplied_hash = event.get("record_hash")
        body = {key: value for key, value in event.items() if key != "record_hash"}
        expected_hash = hashlib.sha256(_canonical(body)).hexdigest()
        if event.get("previous_hash") != previous_hash or supplied_hash != expected_hash:
            return {"valid": False, "records_checked": index - 1, "broken_record": index}
        previous_hash = supplied_hash
    return {"valid": True, "records_checked": len(events), "latest_hash": previous_hash if events else GENESIS}
