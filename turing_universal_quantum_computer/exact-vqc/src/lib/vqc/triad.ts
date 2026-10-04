/** Chronus · Theseus · Ovid, as the SKU contract, on exact arithmetic.

The folded masks are the working form. Bytes appear only at materialise.
The prime composite is the address. The sunflower rank is the slot.
Search is not implemented here: the docs hand it to an engine this runtime
does not contain. The 11-D direction in that handoff is a float, so it is
not executed. The Active Discovery Engine is documented as a simulated twin.
*/

import { fibonacci } from "./lucas-scale.ts";
import { sha256Of } from "./sha256.ts";
import { sunflowerSlot } from "./store.ts";

const MODULUS = (1n << 61n) - 1n;

type Mask = { offset: number; mask: bigint };

type Record = {
  id: string;
  length: number;
  digest: string;
  primary: Mask[];
  replica: Mask[];
  slot: number;
  address: bigint;
  parity: 1 | -1;
};

function modPow(base: bigint, exponent: bigint, modulus: bigint): bigint {
  let result = 1n;
  let factor = base % modulus;
  let cursor = exponent;
  while (cursor > 0n) {
    if (cursor & 1n) result = (result * factor) % modulus;
    factor = (factor * factor) % modulus;
    cursor >>= 1n;
  }
  return result;
}

function chunk(bytes: Uint8Array, offset: number, width: number): bigint {
  let value = 0n;
  for (let index = 0; index < width; index++) {
    const byte = offset + index < bytes.length ? BigInt(bytes[offset + index]) : 0n;
    value = (value << 8n) + byte;
  }
  return value;
}

function zeckendorfMask(value: bigint): bigint {
  if (value === 0n) return 0n;
  let hi = 2;
  while (fibonacci(hi) <= value) hi += 1;
  let mask = 0n;
  let remaining = value;
  for (let index = hi - 1; index >= 2; index--) {
    const limb = fibonacci(index);
    if (limb <= remaining) {
      mask |= 1n << BigInt(index - 2);
      remaining -= limb;
    }
  }
  if (remaining !== 0n) throw new Error("Zeckendorf mask did not consume the chunk");
  return mask;
}

function nonAdjacent(mask: bigint): boolean {
  return (mask & (mask << 1n)) === 0n;
}

function decodeMask(mask: bigint): bigint {
  let value = 0n;
  let bit = 0n;
  let cursor = mask;
  while (cursor > 0n) {
    if (cursor & 1n) value += fibonacci(Number(bit) + 2);
    cursor >>= 1n;
    bit += 1n;
  }
  return value;
}

function fold(bytes: Uint8Array): Mask[] {
  const masks: Mask[] = [];
  for (let offset = 0; offset < bytes.length || (bytes.length === 0 && offset === 0); offset += 8) {
    if (bytes.length === 0) break;
    const mask = zeckendorfMask(chunk(bytes, offset, 8));
    if (!nonAdjacent(mask)) throw new Error("fold produced an adjacent mask");
    masks.push({ offset, mask });
    if (offset + 8 >= bytes.length) break;
  }
  return masks;
}

function materialise(masks: Mask[], length: number): Uint8Array {
  const out = new Uint8Array(masks.length * 8);
  for (const block of masks) {
    let value = decodeMask(block.mask);
    for (let index = 7; index >= 0; index--) {
      out[block.offset + index] = Number(value & 0xffn);
      value >>= 8n;
    }
  }
  return out.slice(0, length);
}

function primeAddress(bytes: Uint8Array): bigint {
  let composite = 1n;
  let used = false;
  for (let offset = 0; offset < Math.max(bytes.length, 1); offset += 7) {
    if (bytes.length === 0) break;
    const exponent = chunk(bytes, offset, 7);
    if (exponent === 0n) continue;
    const prime = [2n, 3n, 5n, 7n, 11n][Math.floor(offset / 7) % 5];
    composite = (composite * modPow(prime, exponent % MODULUS, MODULUS)) % MODULUS;
    used = true;
    if (offset + 7 >= bytes.length) break;
  }
  return used ? composite : 1n;
}

function copy(masks: Mask[]): Mask[] {
  return masks.map((block) => ({ offset: block.offset, mask: block.mask }));
}

export class Triad {
  private records = new Map<string, Record>();
  private next = 0;

  put(bytes: Uint8Array): Record {
    const primary = fold(bytes);
    const digest = sha256Of(bytes);
    const unfolded = materialise(primary, bytes.length);
    if (unfolded.length !== bytes.length || sha256Of(unfolded) !== digest) {
      throw new Error("fold did not round-trip before custody");
    }
    const id = `r${this.next}`;
    const record: Record = {
      id,
      length: bytes.length,
      digest,
      primary,
      replica: copy(primary),
      slot: sunflowerSlot(this.next % 32),
      address: primeAddress(bytes),
      parity: this.next % 2 === 0 ? 1 : -1,
    };
    this.records.set(id, record);
    this.next += 1;
    return record;
  }

  private intact(record: Record, masks: Mask[]): boolean {
    if (masks.some((block) => !nonAdjacent(block.mask))) return false;
    try {
      const bytes = materialise(masks, record.length);
      return sha256Of(bytes) === record.digest;
    } catch {
      return false;
    }
  }

  get(id: string): Uint8Array {
    const record = this.records.get(id);
    if (!record) throw new Error(`unknown record ${id}`);
    if (!this.intact(record, record.primary)) throw new Error(`REFUSED: ${id} failed closed`);
    return materialise(record.primary, record.length);
  }

  damage(id: string): void {
    const record = this.records.get(id);
    if (!record || record.primary.length === 0) throw new Error(`unknown record ${id}`);
    const width = record.primary[0].mask.toString(2).length;
    record.primary[0].mask ^= 1n << BigInt(width - 1);
  }

  heal(id: string): string {
    const record = this.records.get(id);
    if (!record) throw new Error(`unknown record ${id}`);
    if (!this.intact(record, record.replica)) return `REFUSED: ${id} replica is not intact`;
    record.primary = copy(record.replica);
    return `${id} restored from replica`;
  }

  handoff(): string {
    return [
      "handoff = REFUSED",
      "  geodesic search is not implemented inside Theseus",
      "  Intelligence.search_crystal is not in this runtime",
      "  the 11-D direction in the source is a float and is not executed",
      "  DIM = 11 remains the engine's width, not a computation here",
      "  the Active Discovery Engine is a simulated twin in the docs and is not run",
      "  bind_chronus = False",
    ].join("\n");
  }
}

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function triadScript(): string {
  const triad = new Triad();
  const payload = new Uint8Array([0x01]);
  const record = triad.put(payload);
  const opened = hex(triad.get(record.id));
  triad.damage(record.id);
  let refused = "";
  try {
    triad.get(record.id);
    refused = "get returned a damaged record";
  } catch (error) {
    refused = error instanceof Error ? error.message : "refused";
  }
  const healed = triad.heal(record.id);
  const restored = hex(triad.get(record.id));
  if (opened !== "01" || restored !== "01") throw new Error("the working form did not materialise to the payload");
  if (!refused.startsWith("REFUSED")) throw new Error("damage did not fail closed");
  return [
    "triad",
    "  contract = fold is the working form; unfold is egress only",
    "  theorem_proven = False",
    "  payload = 01",
    `  working mask = ${record.primary[0].mask}`,
    "  non-adjacent = True",
    "  bytes are not the stored form",
    `  digest = ${record.digest}`,
    `  prime address = ${record.address}`,
    `  sunflower slot = ${record.slot}`,
    `  Cassini parity = ${record.parity}`,
    `  materialise = ${opened}`,
    `  after damage = ${refused}`,
    `  heal = ${healed}`,
    `  materialise = ${restored}`,
    triad.handoff(),
  ].join("\n");
}
