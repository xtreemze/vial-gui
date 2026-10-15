import json
import pytest
from protocol.halcyon_palette import validate_palette
from protocol.rgb_profiles import RGBProfileCapabilities


def caps():
    return RGBProfileCapabilities(bytes([0xF0, 1, 1, 15, 13, 4, 32, 190, 10, 31, 1]))


def test_rejects_invalid_document_before_device_writes():
    plan = {
        "version": 1,
        "rgb": [
            {
                "scope": 1,
                "index": 13,
                "rgb": {"mode": 1, "hue": 0, "saturation": 210, "brightness": 190, "speed": 128},
            }
        ],
        "tftLayers": [],
        "tftModifiers": [],
    }
    with pytest.raises(ValueError):
        validate_palette(plan, caps(), None)


def test_accepts_web_export_shape():
    plan = json.loads('{"version":1,"rgb":[],"tftLayers":[],"tftModifiers":[]}')
    assert validate_palette(plan, caps(), None) == plan


def test_runtime_apply_save_and_rollback(monkeypatch):
    from protocol.halcyon_palette import PaletteBatch, RgbProtocol as RGB, TftProtocol as TFT
    from protocol.rgb_profiles import RGBProfile

    class Keyboard:
        dev = object()

    keyboard = Keyboard()
    state = [RGBProfile(255, 0, 0, 0, 10)]
    saved = []
    monkeypatch.setattr(RGB, "probe", lambda _kb: caps())
    monkeypatch.setattr(TFT, "probe", lambda _kb: None)
    monkeypatch.setattr(RGB, "get_profile", lambda *_args: state[0])
    monkeypatch.setattr(RGB, "set_profile", lambda _kb, _s, _i, p: state.__setitem__(0, p))
    monkeypatch.setattr(RGB, "save", lambda _kb: saved.append(True))
    plan = {
        "version": 1,
        "rgb": [
            {
                "scope": 1,
                "index": 0,
                "rgb": {"mode": 1, "hue": 40, "saturation": 210, "brightness": 190, "speed": 128},
            }
        ],
        "tftLayers": [],
        "tftModifiers": [],
    }
    batch = PaletteBatch(keyboard, plan)
    batch.apply()
    assert state[0].mode == 1 and state[0].hue == 40
    assert not saved
    batch.restore()
    assert state[0].mode == 255
    batch.apply()
    batch.save()
    assert saved == [True]
    batch = PaletteBatch(keyboard, plan)
    with pytest.raises(RuntimeError, match="cancelled"):
        batch.apply(lambda _d, _t: False)
    assert saved == [True]
    keyboard.dev = object()
    with pytest.raises(RuntimeError, match="session changed"):
        batch.apply()


def test_accepts_canonical_web_generator_document():
    from pathlib import Path
    from protocol.halcyon_settings import HalcyonCapabilities
    tft = HalcyonCapabilities(bytes([0xf1, 1, 1, 3, 13, 10, 1, 5, 100, 100, 1, 1]))
    path = Path(__file__).resolve().parents[4] / "docs" / "palette-v1.json"
    plan = validate_palette(json.loads(path.read_text()), caps(), tft)
    assert len(plan["rgb"]) == 50
    assert len(plan["tftModifiers"]) == 10
