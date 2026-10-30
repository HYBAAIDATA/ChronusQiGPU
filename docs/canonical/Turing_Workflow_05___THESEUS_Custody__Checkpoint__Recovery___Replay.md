# Turing Workflow 05 — THESEUS Custody, Checkpoint, Recovery & Replay

## Purpose

Use THESEUS as Turing's durable custody/continuity service without moving VQC semantic authority into custody.

## Custody object

Turing program/circuit identity; state/checkpoint representation; exactness metadata; OVID transform metadata if applicable; backend history; measurement/results; hashes; lineage; environment; release versions; policy; replay instructions.

## Required tests

Checkpoint→restore equality; restart continuity; replica recovery; journal replay; corrupt checkpoint rejection; incomplete-write recovery; version migration; rollback; duplicate/replay protection; retention/quotas; evidence preservation.

## Rule

THESEUS preserves and recovers the state Turing declares valid. It must not reinterpret circuits, change representation semantics, or promote a result.

## Production gate

A checkpoint path is production-supported only when restore/replay is demonstrated from the exact released artifacts.