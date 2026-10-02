# Chronus evidence schemas

`evidence.schema.json` fixes emulator evidence v1. Evidence is canonical JSON (`sort_keys`, compact separators, no NaN). Its SHA-256 is the content address. The executable and final committed VRAM are independently digested. Trap runs are retained as rejected evidence and never represented as successful execution.
