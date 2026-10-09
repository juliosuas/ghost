# Screenshots

Checked-in SVG captures used by the README:

- `doctor.svg` — `ghost doctor`
- `case-list.svg` — `ghost list`
- `case-show.svg` — `ghost show <id-prefix>`

## Demo GIF

`demo.gif` shows `ghost import`, `ghost list`, `ghost show`, and `ghost export`
against the synthetic sample case in `examples/` (`demo_user`, fake data only).
Every frame is real CLI output, rendered by
[`scripts/render_demo_gif.py`](../../scripts/render_demo_gif.py) so it can be
regenerated after CLI changes. It does not run `ghost investigate`, which would
send live HTTP probes; a screen recording of an authorized self-audit can
replace it later.
