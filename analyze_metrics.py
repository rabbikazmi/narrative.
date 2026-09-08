import json
import sys
from collections import defaultdict
from pathlib import Path


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def report_latency(events: list[dict], metric_type: str, label: str) -> None:
    values = [event["value_ms"] for event in events if event["metric_type"] == metric_type]
    print(f"{label}: n={len(values)}, p50={percentile(values, 50):.2f} ms, p95={percentile(values, 95):.2f} ms")


def main(path: str = "logs/metrics.jsonl") -> None:
    events = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    report_latency(events, "interrupt_to_silence", "Interrupt-to-silence latency")
    audio = [event for event in events if event["metric_type"] == "time_to_first_audio"]
    for temperature in ("cold", "warm"):
        report_latency(
            [event for event in audio if event.get("cold_warm") == temperature],
            "time_to_first_audio",
            f"Time-to-first-audio ({temperature})",
        )

    recognition = [
        event for event in events
        if event["metric_type"] == "command_recognition" and event.get("pass_fail") is not None
    ]
    passed = sum(event["pass_fail"] == "pass" for event in recognition)
    accuracy = 100 * passed / len(recognition) if recognition else 0
    print(f"Command recognition accuracy: {accuracy:.2f}% ({passed}/{len(recognition)})")
    by_type: dict[str, list[bool]] = defaultdict(list)
    for event in recognition:
        by_type[event.get("command_spoken", "unknown")].append(event["pass_fail"] == "pass")
    for command_type, results in sorted(by_type.items()):
        print(f"  {command_type}: {100 * sum(results) / len(results):.2f}% ({sum(results)}/{len(results)})")

    state = [
        event for event in events
        if event["metric_type"] == "state_correctness" and event.get("pass_fail") is not None
    ]
    state_passed = sum(event["pass_fail"] == "pass" for event in state)
    print(f"State-correctness pass rate: {state_passed}/{len(state)} passed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "logs/metrics.jsonl")