"""Wybór urządzeń wejściowych (bez prawdziwego sprzętu: dane jak z sounddevice)."""

from osciviz.core.audio_source import is_virtual_cable, select_input_devices

HOSTAPIS = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}]
DEVICES = [
    {"name": "CABLE Output (VB-Audio Virtual ", "hostapi": 0, "max_input_channels": 2},
    {"name": "Speakers (Realtek)", "hostapi": 0, "max_input_channels": 0},
    {"name": "CABLE Output (VB-Audio Virtual Cable)", "hostapi": 1, "max_input_channels": 2},
    {"name": "CABLE Output (VB-Audio Virtual Cable)", "hostapi": 2, "max_input_channels": 2},
    {"name": "Microphone (USB)", "hostapi": 2, "max_input_channels": 1},
]


def test_windows_keeps_only_wasapi():
    result = select_input_devices(DEVICES, HOSTAPIS, "win32")
    assert [d["index"] for d in result] == [3, 4]
    assert result[0]["is_virtual"] and not result[1]["is_virtual"]


def test_macos_keeps_all_inputs():
    devices = [{"name": "BlackHole 2ch", "hostapi": 0, "max_input_channels": 2},
               {"name": "MacBook Pro Speakers", "hostapi": 0, "max_input_channels": 0}]
    result = select_input_devices(devices, [{"name": "Core Audio"}], "darwin")
    assert len(result) == 1 and result[0]["is_virtual"]


def test_windows_without_wasapi_falls_back_to_all():
    result = select_input_devices(DEVICES, [{"name": "MME"}], "win32")
    assert len(result) == 4


def test_virtual_cable_names():
    assert is_virtual_cable("BlackHole 16ch")
    assert is_virtual_cable("CABLE Output (VB-Audio Virtual Cable)")
    assert not is_virtual_cable("Mikrofon (Realtek High Definition Audio)")
