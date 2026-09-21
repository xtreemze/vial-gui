# Desktop configurator convergence plan

The xtreemze desktop configurator currently inherits Vial's Python 3.6, PyQt5, fbs, and PyInstaller 3-era application stack. This remains the compatibility baseline while the next-generation UI is developed.

The target is not a second independent desktop rewrite. The target is one shared configurator UI/domain/protocol implementation used by:

- the browser client through WebHID; and
- the desktop client through a thin Tauri shell with a native Rust HID adapter.

The browser-side migration is tracked in `xtreemze/vial-web#10` and its foundation PR `xtreemze/vial-web#11`.

## Constraints

1. Do not disrupt the custom Halcyon editor work in PR #6.
2. Preserve standard Vial behavior before retiring Python.
3. Preserve xtreemze command compatibility:
   - `0xF0` RGB profile protocol
   - `0xF1` Halcyon settings/telemetry
   - planned `0xF2` TFT configuration from `xtreemze/qmk_userspace#68`
4. Keep firmware schema changes out of the UI migration.
5. Desktop hardware access must use a native transport; desktop functionality must not depend on browser WebHID availability.
6. Keep transport objects out of UI components and keep packet codecs out of the Tauri shell.
7. Retain the Python application until the parity matrix is complete and hardware behavior is accepted.

## Target boundary

```text
shared React UI
      |
shared device/domain state
      |
shared Vial + Halcyon protocol codecs
      |
KeyboardTransport
      |
      +-- WebHID adapter (browser)
      |
      +-- Tauri/Rust HID adapter (desktop)
```

The Rust side should stay deliberately small: enumerate/open/close devices, exchange HID reports, surface disconnect/reconnect, and expose only the permissions needed for those operations.

## Migration sequence

1. Treat the current Python application as the behavioral reference.
2. Stabilize the firmware-facing ABI through `xtreemze/qmk_userspace#73` / PR #74.
3. Build the browser-native transport/domain foundation in `vial-web`.
4. Establish the shared UI/protocol package boundary.
5. Add a minimal Tauri shell and native HID adapter.
6. Port editor surfaces incrementally and update the parity matrix per PR.
7. Add package/sign/notarization workflows for macOS, Windows, and Linux.
8. Verify real-device reconnect, suspend/resume, multiple-device selection, and import/export behavior.
9. Retire Python/fbs/PyInstaller only after the parity matrix has no blocking gaps.

## Transitional Python maintenance

Changes to the existing Python client remain appropriate for user-facing bugs, protocol compatibility, and current Halcyon work. Large framework modernization should be justified as a migration blocker; otherwise effort should go into the shared replacement rather than maintaining two long-lived UI architectures.
