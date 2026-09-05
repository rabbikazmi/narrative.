import json
import logging
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger("voice_reader")


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, default=str))
