# Desktop migration parity matrix

This matrix is a required migration artifact. A row can move to **accepted** only when behavior is implemented in the shared client, exercised through the desktop transport where applicable, and has suitable automated or hardware evidence.

| Surface | Python/PyQt reference | Shared/Tauri target | Evidence required |
| --- | --- | --- | --- |
| Device discovery and selection | Implemented | Pending | native enumeration + selection tests |
| Open/close lifecycle | Implemented | Pending | automated transport tests |
| Disconnect/reconnect | Implemented/current behavior | Pending | physical unplug/replug acceptance |
| Import/export configuration | Implemented | Pending | round-trip fixture tests |
| Keymap editor | Implemented | Pending | parity fixture + interaction tests |
| Layout editor | Implemented | Pending | parity fixture |
| Keycode browser/search | Implemented | Pending | semantic/keyboard navigation tests |
| Macro editor/recorder | Implemented | Pending | round-trip and lifecycle tests |
| Combos | Implemented | Pending | protocol fixture tests |
| Tap Dance | Implemented | Pending | protocol fixture tests |
| Key Override | Implemented | Pending | protocol fixture tests |
| Alt Repeat Key | Implemented | Pending | ordered-pair parity tests |
| QMK Settings | Implemented | Pending | capability and read/write tests |
| Lighting / VialRGB | Implemented | Pending | capability/read/write tests |
| Matrix test | Implemented | Pending | live-device acceptance |
| Firmware flasher | Implemented | Pending / decision required | platform-specific safety review |
| xtreemze RGB profiles `0xF0` | Implemented | Pending | shared ABI golden vectors |
| Halcyon settings/telemetry `0xF1` | Implemented | Pending | shared ABI golden vectors |
| TFT labels/patterns `0xF2` | PR #6 / firmware #68 | Pending | final ABI vectors after merge |
| Theme/density behavior | Implemented | Pending | visual/accessibility checks |
| Keyboard-only operation | Partial/current | Pending | automated accessibility tests |
| Touch/pointer behavior | Qt-dependent | Pending | browser + desktop interaction tests |
| macOS package | Implemented | Pending | signed/notarized CI artifact |
| Windows package/installer | Implemented | Pending | CI artifact + install smoke test |
| Linux package | Implemented | Pending | CI artifact + device permission smoke test |

## Rules

- Do not mark a row accepted solely because a screen renders.
- Protocol rows require byte-level request/response evidence.
- Hardware lifecycle rows require physical-device evidence where mocks cannot prove behavior.
- If a legacy feature should not be carried forward, record an explicit decision and rationale rather than silently omitting the row.
