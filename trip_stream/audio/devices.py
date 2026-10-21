"""Audio input device enumeration (PortAudio via sounddevice)."""

from __future__ import annotations

TONE_DEVICE = "__tone__"

try:
    import sounddevice as sd
except (ImportError, OSError):  # PortAudio missing
    sd = None


def available() -> bool:
    return sd is not None


def device_label(dev: dict, hostapis) -> str:
    api = hostapis[dev["hostapi"]]["name"] if hostapis else ""
    return f"{dev['name']} [{api}]" if api else dev["name"]


def list_input_devices() -> list[dict]:
    """Return input devices as dicts: {label, index, channels, samplerate}."""
    if sd is None:
        return []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return []
    out = []
    for index, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            out.append({
                "label": device_label(dev, hostapis),
                "index": index,
                "channels": int(dev["max_input_channels"]),
                "samplerate": int(dev.get("default_samplerate") or 44100),
            })
    return out


def find_device(label: str):
    """Resolve a saved device label to a PortAudio index (None = system default)."""
    if not label:
        return None
    for dev in list_input_devices():
        if dev["label"] == label:
            return dev["index"]
    # fall back to a match on the name only (host API may have changed)
    name = label.split(" [")[0]
    for dev in list_input_devices():
        if dev["label"].split(" [")[0] == name:
            return dev["index"]
    raise LookupError(label)


def device_channels(label: str) -> int:
    if label == TONE_DEVICE:
        return 2
    if sd is None:
        return 2
    try:
        index = find_device(label)
        info = sd.query_devices(index, "input") if index is not None else sd.query_devices(kind="input")
        return max(1, int(info["max_input_channels"]))
    except Exception:
        return 2
