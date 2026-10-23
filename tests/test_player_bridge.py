import time

import requests
from PyQt5.QtCore import QCoreApplication

from lingua.player_bridge import PlayerBridge


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def test_playback_time_and_seek_command_round_trip():
    _app()
    bridge = PlayerBridge()
    assert bridge.start()
    try:
        payload = {
            "session_id": "tab:frame",
            "title": "Test video",
            "url": "https://example.test/video",
            "current_time": 123.5,
            "duration": 3600,
            "paused": False,
            "can_seek": True,
            "viewport_area": 800000,
            "last_command_sequence": 0,
        }
        response = requests.post(
            f"http://127.0.0.1:{bridge.port}/api/playback",
            json=payload,
            timeout=2,
        )
        assert response.status_code == 200
        assert bridge.is_connected
        state = bridge.state
        assert state is not None
        assert state.title == "Test video"
        estimated = bridge.time_at(time.monotonic() + 2)
        assert estimated is not None and estimated >= 125.5

        assert bridge.seek(4321.0)
        response = requests.post(
            f"http://127.0.0.1:{bridge.port}/api/playback",
            json=payload,
            timeout=2,
        )
        command = response.json()["command"]
        assert command["target_session"] == "tab:frame"
        assert command["time"] == 4321.0
    finally:
        bridge.stop()


def test_manual_player_sync():
    _app()
    bridge = PlayerBridge()
    assert bridge.set_manual_position(754)
    state = bridge.state
    assert state is not None and state.manual
    assert bridge.is_connected
    assert not bridge.seek(30)
