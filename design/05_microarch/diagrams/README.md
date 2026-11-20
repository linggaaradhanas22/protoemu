# ProtoEmu diagram conventions

- Use **solid arrows for data**: program words, payloads, pin values, capture results and numeric timestamps.
- Use **dashed arrows for control and status**: requests, handshakes, enables, and run or stop signals.
- When an interface carries both, draw separate, labeled arrows and show the direction of each. These are logical paths: separate arrows do not imply separate physical pins.
- Include the line-style key on each diagram. This project convention takes precedence over the draw.io hardware preset's default line styles.

Keep the editable `.drawio` and exported `.svg` together. Publish revisions as a new file pair and leave older pairs intact.
