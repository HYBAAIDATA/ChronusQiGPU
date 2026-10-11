# Chronus-1 executable container v1.1

All integers and instructions are little-endian. The container is canonical: one logical executable has one byte representation.

## Header — 32 bytes

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | `CHRN` |
| 4 | 2 | major = 1 |
| 6 | 2 | minor >= 1 |
| 8 | 4 | flags; zero in v1.1 |
| 12 | 4 | aligned entry PC |
| 16 | 4 | code word count |
| 20 | 4 | required committed global bytes |
| 24 | 4 | CRC32 of the complete code+metadata payload |
| 28 | 4 | metadata byte count |

The exact file size is `32 + code_words*4 + metadata_bytes`. Extra bytes, truncation, checksum mismatch, unsupported major version, an entry outside code, or insufficient committed memory trap before dispatch.

## Metadata

`META`, `symbol_count:u32`, `reconvergence_count:u32`, `reserved:u32=0`, followed by symbol records and reconvergence records.

A symbol record is `name_bytes:u16, kind:u8, flags:u8, value:u32, size:u32, utf8_name, zero_padding_to_4`. Names are non-empty, unique UTF-8 strings of at most 255 bytes. Padding must be zero.

A reconvergence record is `branch_pc:u32, reconverge_pc:u32`. Both are aligned, inside code, and each branch PC occurs at most once. Every dynamically divergent `BRAZ/BRANZ` must have a record. The emulator traps a divergent branch without one.

## Checksum authority

CRC32 polynomial `0xEDB88320` covers every byte after the header: code and metadata. It detects corruption; it is not an identity signature. Signed production evidence remains a separate attestation layer.
