# Sky130 layout flow — blocked, not sign-off

Target: OpenLane 1 tag `2023.09.07`, `sky130A` and `sky130_fd_sc_hd`, with the PDK/tool versions supplied by that release. Its `dependencies/tool_metadata.yml` lists open_pdks `1341f54f5ce0c4955326297f235e4ace1eb6d419`, Yosys `14d50a176d59a5eac95a57a01f9e933297251d5b`, OpenROAD `0a6d0fd469bc674417036342994520ee2e0a2727`, Magic `0afe4d87d4aacfbbb2659129a1858a22d216a920` and Netgen `87d8759a6980d297edcb9be6f8661867e4726f9a`. Use that release's installation and PDK instructions; retain actual image digest, tool versions and PDK provenance in a real run.

Run `bash hw/openlane/run_zeckendorf.sh` inside the pinned OpenLane environment with the repository mounted and `PDK_ROOT` set. Set `OPENLANE_FLOW` if the flow is not `/openlane/flow.tcl`. Configuration is a starting point, **not validated**: the SystemVerilog front-end, constraints and physical configuration may require changes. A complete run must independently inspect and retain DRC, LVS, timing and netlist/layout reports. Static timing does not prove constant-cycle behavior; separately define and verify a cycle-latency property. No result here establishes tape-out readiness.

Reference: https://openlane.readthedocs.io/en/2023.09.07/getting_started/quickstart.html and the tagged `dependencies/tool_metadata.yml`.
