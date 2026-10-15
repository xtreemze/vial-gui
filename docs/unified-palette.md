# Import a unified RGB/TFT palette

In the RGB profile editor, choose **Import unified RGB / TFT palette** and paste
the v1 JSON exported by Vial Web's browser-native palette card. Explicit targets
are validated against fresh 0xF0/0xF1 capabilities before device mutation. Remove
entries from JSON to preserve exceptions. The GUI consumes explicit colors and
does not duplicate the generator or firmware precedence resolver.

Preview snapshots every target, applies runtime colors, verifies readback and
rolls back on cancellation/failure. Save permanently verifies again before the
sequential RGB and TFT save commands. A partial save can leave one store durable;
a runtime Restore does not reverse that durable write. Closing an unsaved
preview restores its original runtime colors. Transport failures are reported
and rollback is best effort, with every target attempted.

Neither save ACK nor readback certifies persistence on both master halves.
Physical testing and firmware RGB split replication remain tracked in
qmk_userspace #16/#101 and vial-web #40. Protocol v1 has no TFT combo accent;
0xF2 display labels/patterns remain independent.
