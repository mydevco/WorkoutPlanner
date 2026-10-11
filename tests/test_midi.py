import unittest
from types import SimpleNamespace

from backend.midi import MidiService, UnavailableMidiBackend, _event_from_short_message, map_note_to_pad, parse_midi_message


class FakePort:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeBackend:
    def __init__(self):
        self.names = ["Practice Controller"]
        self.callback = None
        self.port = FakePort()

    def get_input_names(self):
        return self.names

    def open_input(self, name, callback):
        self.callback = callback
        return self.port


class MidiTest(unittest.TestCase):
    def test_note_mapping_and_note_on_parsing(self):
        self.assertEqual(map_note_to_pad(36), 0)
        self.assertEqual(map_note_to_pad(43), 7)
        self.assertIsNone(map_note_to_pad(60))
        event = parse_midi_message(SimpleNamespace(type="note_on", note=39, velocity=100, channel=2))
        self.assertEqual(event.as_dict(), {"pad": 3, "note": 39, "velocity": 100, "channel": 2})
        self.assertIsNone(parse_midi_message(SimpleNamespace(type="note_off", note=36, velocity=100)))
        self.assertIsNone(parse_midi_message(SimpleNamespace(type="note_on", note=36, velocity=0)))
        self.assertEqual(_event_from_short_message(0x642790).as_dict(), {
            "pad": 3, "note": 39, "velocity": 100, "channel": 0
        })
        self.assertIsNone(_event_from_short_message(0x64392780))

    def test_device_lifecycle_and_event_polling(self):
        backend = FakeBackend()
        service = MidiService(backend)
        self.assertEqual(service.devices(), ["Practice Controller"])
        self.assertTrue(service.connect("Practice Controller")["connected"])
        backend.callback(SimpleNamespace(type="note_on", note=36, velocity=127, channel=0))
        self.assertEqual(service.poll()[0]["pad"], 0)
        self.assertEqual(service.poll(), [])
        service.disconnect()
        self.assertTrue(backend.port.closed)
        self.assertFalse(service.status()["connected"])

    def test_disconnect_is_detected_during_poll(self):
        backend = FakeBackend()
        service = MidiService(backend)
        service.connect("Practice Controller")
        backend.names = []
        service.poll()
        self.assertFalse(service.status()["connected"])
        self.assertIn("disconnected", service.status()["error"])

    def test_unavailable_backend_is_safe(self):
        service = MidiService(UnavailableMidiBackend())
        self.assertEqual(service.devices(), [])
        self.assertFalse(service.status()["available"])
        with self.assertRaises(ValueError):
            service.connect("")


if __name__ == "__main__":
    unittest.main()
