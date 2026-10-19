# Research evidence

`local/` and `raw/` are ignored runtime output, not source. The experiment runner
produces uniquely named JSON manifests with explicit status and source identity.
`manifests/` is for reviewed immutable run records or checksum-addressed archive
references. `summaries/` contains only reproducibly generated data with its input
manifest identified. No hand-edited values, credentials or bulk private data.

This initial organization change does not invent a publication dataset. CI
collects fresh evidence on the pushed Git commit and uploads it as artifacts.
Local package validation remains labelled development evidence when it does not
come from a clean, commit-bound checkout.
