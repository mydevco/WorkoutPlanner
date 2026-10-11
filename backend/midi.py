"""Optional native MIDI input service used by the practice page."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
from typing import Callable, Protocol


PAD_NOTES = tuple(range(36, 44))


class MidiPort(Protocol):
    def close(self) -> None: ...


class MidiBackend(Protocol):
    def get_input_names(self) -> list[str]: ...

    def open_input(self, name: str, callback: Callable[[object], None]) -> MidiPort: ...


@dataclass(frozen=True)
class MidiEvent:
    pad: int
    note: int
    velocity: int
    channel: int

    def as_dict(self) -> dict[str, int]:
        return {
            "pad": self.pad,
            "note": self.note,
            "velocity": self.velocity,
            "channel": self.channel,
        }


def map_note_to_pad(note: int, pad_notes: tuple[int, ...] = PAD_NOTES) -> int | None:
    """Return the zero-based pad for a MIDI note, or None when it is unmapped."""
    try:
        return pad_notes.index(note)
    except ValueError:
        return None


def parse_midi_message(message: object, pad_notes: tuple[int, ...] = PAD_NOTES) -> MidiEvent | None:
    """Convert a mido-like note-on message into a practice event."""
    if getattr(message, "type", None) != "note_on":
        return None
    velocity = int(getattr(message, "velocity", 0))
    if velocity <= 0:
        return None
    note = int(getattr(message, "note", -1))
    pad = map_note_to_pad(note, pad_notes)
    if pad is None:
        return None
    return MidiEvent(pad=pad, note=note, velocity=min(127, velocity), channel=int(getattr(message, "channel", 0)))


class UnavailableMidiBackend:
    def get_input_names(self) -> list[str]:
        return []

    def open_input(self, name: str, callback: Callable[[object], None]) -> MidiPort:
        raise RuntimeError("The native MIDI backend is unavailable.")


def create_mido_backend() -> MidiBackend:
    try:
        import mido
    except ImportError:
        return UnavailableMidiBackend()

    class MidoBackend:
        def get_input_names(self) -> list[str]:
            return list(mido.get_input_names())

        def open_input(self, name: str, callback: Callable[[object], None]) -> MidiPort:
            return mido.open_input(name, callback=callback)

    return MidoBackend()


class MidiService:
    """Thread-safe device lifecycle and event queue around a native MIDI backend."""

    def __init__(self, backend: MidiBackend | None = None):
        self.backend = backend or create_mido_backend()
        self._port: MidiPort | None = None
        self._device: str | None = None
        self._error: str | None = None
        self._events: deque[MidiEvent] = deque(maxlen=100)
        self._lock = threading.RLock()

    def devices(self) -> list[str]:
        try:
            return self.backend.get_input_names()
        except Exception as error:
            with self._lock:
                self._error = f"Could not enumerate MIDI inputs: {error}"
            return []

    def connect(self, name: str) -> dict:
        name = name.strip()
        if not name:
            raise ValueError("Choose a MIDI input device.")
        if name not in self.devices():
            raise ValueError("That MIDI input is no longer available. Refresh the device list.")
        self.disconnect()
        try:
            port = self.backend.open_input(name, self._on_message)
        except Exception as error:
            with self._lock:
                self._error = f"Could not connect to MIDI input: {error}"
            raise RuntimeError(self._error) from error
        with self._lock:
            self._port = port
            self._device = name
            self._error = None
        return self.status()

    def disconnect(self) -> dict:
        with self._lock:
            port, self._port = self._port, None
            self._device = None
        if port is not None:
            try:
                port.close()
            except Exception as error:
                with self._lock:
                    self._error = f"Could not close MIDI input: {error}"
        return self.status()

    def poll(self) -> list[dict[str, int]]:
        with self._lock:
            connected_device = self._device
        if connected_device is not None:
            try:
                still_present = connected_device in self.backend.get_input_names()
            except Exception as error:
                still_present = True
                with self._lock:
                    self._error = f"Could not check MIDI input: {error}"
            if not still_present:
                with self._lock:
                    port, self._port = self._port, None
                    self._device = None
                    self._error = f"MIDI input disconnected: {connected_device}"
                if port is not None:
                    try:
                        port.close()
                    except Exception as error:
                        with self._lock:
                            self._error = f"MIDI input disconnected and could not close cleanly: {error}"
        with self._lock:
            events = list(self._events)
            self._events.clear()
        return [event.as_dict() for event in events]

    def status(self) -> dict:
        with self._lock:
            return {
                "available": not isinstance(self.backend, UnavailableMidiBackend),
                "connected": self._device is not None,
                "device": self._device,
                "error": self._error,
            }

    def close(self) -> None:
        self.disconnect()

    def _on_message(self, message: object) -> None:
        event = parse_midi_message(message)
        if event is not None:
            with self._lock:
                self._events.append(event)
