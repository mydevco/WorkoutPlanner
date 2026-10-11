"""Optional native MIDI input service used by the practice page."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading
import sys
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


def _event_from_short_message(message: int) -> MidiEvent | None:
    """Decode a packed WinMM short MIDI message."""
    status = message & 0xFF
    if status & 0xF0 != 0x90:
        return None
    return parse_midi_message(
        type("WinMMMessage", (), {
            "type": "note_on",
            "note": (message >> 8) & 0xFF,
            "velocity": (message >> 16) & 0xFF,
            "channel": status & 0x0F,
        })()
    )


class WindowsMidiBackend:
    """Windows Multimedia (winmm) MIDI input backend with no third-party DLL."""

    def __init__(self):
        import ctypes

        self._ctypes = ctypes
        self._winmm = ctypes.WinDLL("winmm")
        self._ports: set[WindowsMidiPort] = set()
        self._callback_type = ctypes.WINFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )

    def get_input_names(self) -> list[str]:
        import ctypes

        count = self._winmm.midiInGetNumDevs()
        names = []
        for index in range(count):
            caps = ctypes.create_string_buffer(404)
            result = self._winmm.midiInGetDevCapsW(index, caps, ctypes.sizeof(caps))
            if result == 0:
                names.append(ctypes.wstring_at(ctypes.addressof(caps) + 8))
        return names

    def open_input(self, name: str, callback: Callable[[object], None]) -> MidiPort:
        names = self.get_input_names()
        try:
            index = names.index(name)
        except ValueError as error:
            raise ValueError("That MIDI input is no longer available.") from error
        port = WindowsMidiPort(self, index, callback)
        self._ports.add(port)
        return port

    def _discard(self, port: "WindowsMidiPort") -> None:
        self._ports.discard(port)


class WindowsMidiPort:
    def __init__(self, backend: WindowsMidiBackend, index: int, callback: Callable[[object], None]):
        self._backend = backend
        self._winmm = backend._winmm
        self._ctypes = backend._ctypes
        self._closed = False
        self._callback = callback
        self._callback_ref = backend._callback_type(self._on_callback)
        handle = self._ctypes.c_void_p()
        result = self._winmm.midiInOpen(
            self._ctypes.byref(handle), index, self._callback_ref, None, 0x00030000
        )
        if result != 0:
            raise RuntimeError(f"Windows MIDI input could not be opened (winmm error {result}).")
        self._handle = handle
        result = self._winmm.midiInStart(self._handle)
        if result != 0:
            self.close()
            raise RuntimeError(f"Windows MIDI input could not be started (winmm error {result}).")

    def _on_callback(self, _handle, message_type, _instance, param1, _param2):
        if message_type == 0x3:  # MIM_DATA
            event = _event_from_short_message(int(param1 or 0))
            if event is not None:
                self._callback(type("WinMMMessage", (), {
                    "type": "note_on",
                    "note": event.note,
                    "velocity": event.velocity,
                    "channel": event.channel,
                })())

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._winmm.midiInStop(self._handle)
        self._winmm.midiInReset(self._handle)
        self._winmm.midiInClose(self._handle)
        self._backend._discard(self)


def create_mido_backend() -> MidiBackend:
    if sys.platform == "win32":
        try:
            return WindowsMidiBackend()
        except (AttributeError, OSError):
            pass
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
