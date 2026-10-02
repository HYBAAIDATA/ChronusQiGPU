import {
  createHash,
  createPublicKey,
  randomUUID,
  verify,
} from "node:crypto";

export interface CommandEventInput {
  tenantId: string;
  type: string;
  causalId: string;
  actorId: string;
  actorPublicKeyPem: string;
  actorSignatureBase64: string;
  occurredAt: string;
  payload: Readonly<Record<string, unknown>>;
}

export interface StoredCommandEvent extends CommandEventInput {
  eventId: string;
  sequence: number;
  previousHash: string;
  eventHash: string;
}

export interface EventJournal {
  latest(tenantId: string): Promise<StoredCommandEvent | null>;
  appendIfLatest(
    tenantId: string,
    expectedPreviousHash: string,
    event: StoredCommandEvent,
  ): Promise<boolean>;
  list(tenantId: string, afterSequence?: number): Promise<StoredCommandEvent[]>;
}

export class InMemoryEventJournal implements EventJournal {
  private readonly streams = new Map<string, StoredCommandEvent[]>();
  async latest(tenantId: string): Promise<StoredCommandEvent | null> {
    return this.streams.get(tenantId)?.at(-1) ?? null;
  }
  async appendIfLatest(
    tenantId: string,
    expectedPreviousHash: string,
    event: StoredCommandEvent,
  ): Promise<boolean> {
    const stream = this.streams.get(tenantId) ?? [];
    if ((stream.at(-1)?.eventHash ?? GENESIS_HASH) !== expectedPreviousHash) {
      return false;
    }
    stream.push(event);
    this.streams.set(tenantId, stream);
    return true;
  }
  async list(
    tenantId: string,
    afterSequence = 0,
  ): Promise<StoredCommandEvent[]> {
    return (this.streams.get(tenantId) ?? []).filter(
      ({ sequence }) => sequence > afterSequence,
    );
  }
}

export const GENESIS_HASH = "0".repeat(64);

export class ProvenanceEventStore {
  constructor(private readonly journal: EventJournal) {}

  static signingPayload(input: CommandEventInput): Buffer {
    return Buffer.from(
      canonicalJson({
        actorId: input.actorId,
        causalId: input.causalId,
        occurredAt: input.occurredAt,
        payload: input.payload,
        tenantId: input.tenantId,
        type: input.type,
      }),
    );
  }

  async append(input: CommandEventInput): Promise<StoredCommandEvent> {
    if (!verifyActor(input)) throw new Error("invalid actor signature");
    for (let attempt = 0; attempt < 5; attempt++) {
      const latest = await this.journal.latest(input.tenantId);
      const previousHash = latest?.eventHash ?? GENESIS_HASH;
      const eventWithoutHash = {
        ...input,
        eventId: randomUUID(),
        sequence: (latest?.sequence ?? 0) + 1,
        previousHash,
      };
      const event: StoredCommandEvent = {
        ...eventWithoutHash,
        eventHash: digest(canonicalJson(eventWithoutHash)),
      };
      if (
        await this.journal.appendIfLatest(
          input.tenantId,
          previousHash,
          event,
        )
      ) {
        return event;
      }
    }
    throw new Error("event stream changed concurrently");
  }

  async verifyStream(tenantId: string): Promise<boolean> {
    let previousHash = GENESIS_HASH;
    let expectedSequence = 1;
    for (const event of await this.journal.list(tenantId)) {
      const { eventHash, ...unsignedHashEnvelope } = event;
      if (
        event.sequence !== expectedSequence ||
        event.previousHash !== previousHash ||
        digest(canonicalJson(unsignedHashEnvelope)) !== eventHash ||
        !verifyActor(event)
      ) {
        return false;
      }
      previousHash = eventHash;
      expectedSequence++;
    }
    return true;
  }
}

function verifyActor(input: CommandEventInput): boolean {
  try {
    return verify(
      null,
      ProvenanceEventStore.signingPayload(input),
      createPublicKey(input.actorPublicKeyPem),
      Buffer.from(input.actorSignatureBase64, "base64"),
    );
  } catch {
    return false;
  }
}

function digest(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right));
    return `{${entries
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}