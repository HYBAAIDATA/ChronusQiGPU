'use client';

import React, { FormEvent, useCallback, useEffect, useId, useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import { StatusPill } from '@/components/console/status-pill';
import {
  ChronusAPIClient,
  ChronusAPIError,
  type ALHarasInspectRequest,
  type ALHarasRegisterValue,
  type ApiRecord,
  type VerifyReceiptResponse,
} from '@/lib/api-client';

// AL HARAS (HYBA Security) check demonstrations. Each request body shown on screen is the exact object sent.

const ADMISSION_AGREE: ALHarasInspectRequest = {
  payload: 'example-workload-001',
  state_vectors: [[1, 0], [1, 0], [1, 0]],
  tolerance: '0',
};
const ADMISSION_DISAGREE: ALHarasInspectRequest = {
  payload: 'example-workload-001',
  state_vectors: [[1, 0], [1, 0], [0, 1]],
  tolerance: '0',
};

const AGENTS_AGREE: Record<string, number[]> = {
  Planner: [1, 0, 0, 1],
  Coder: [1, 0, 0, 1],
  Executor: [1, 0, 0, 1],
  Tool: [1, 0, 0, 1],
};
const AGENTS_CODER_ALTERED: Record<string, number[]> = { ...AGENTS_AGREE, Coder: [99, -88, 77, 66] };
const AGENT_STALK_DIM = 4;

const ROUTE_PACKET = 'EXAMPLE_PACKET_001';
const ROUTE_SOURCE = 'SAT_00';
const ROUTE_TARGET = 'SAT_07';

const INFERENCE_INPUT = [12, 24, 36, 48];
const INFERENCE_COMMITMENT = 'example-weights-commitment-v1';

const SETTLEMENT_SENDER = 'CENTRAL_BANK_A';
const SETTLEMENT_RECEIVER = 'CENTRAL_BANK_B';
const SETTLEMENT_AMOUNT = 1000;

const TISA_MULTIPLY = 0x02;
const TISA_CONSISTENCY = 0x03;
const TISA_REGISTERS = { rs1: 1, rs2: 2, rd: 3 };
const MULTIPLY_RS1: ALHarasRegisterValue = [1, 2, 0, 0];
const MULTIPLY_RS2: ALHarasRegisterValue = [3, 1, 0, 0];
const MISMATCH_RS1: ALHarasRegisterValue = [10, 0, 0, 0];
const MISMATCH_RS2: ALHarasRegisterValue = [0, 10, 0, 0];

/** Exact product in Z[ζ5] = Z[x]/(x⁴ + x³ + x² + x + 1), recomputed in the browser as an independent check. */
function multiplyZeta5(a: ALHarasRegisterValue, b: ALHarasRegisterValue): ALHarasRegisterValue {
  const d = [0, 0, 0, 0, 0, 0, 0];
  for (let i = 0; i < 4; i += 1) {
    for (let j = 0; j < 4; j += 1) d[i + j] += a[i] * b[j];
  }
  // Reduce with x⁵ = 1, x⁶ = x and x⁴ = −(1 + x + x² + x³).
  return [d[0] + d[5] - d[4], d[1] + d[6] - d[4], d[2] - d[4], d[3] - d[4]];
}

const MULTIPLY_EXPECTED = multiplyZeta5(MULTIPLY_RS1, MULTIPLY_RS2);
const ZETA_POWERS = ['', 'ζ', 'ζ²', 'ζ³'];

function formatZeta(values: readonly number[]): string {
  let text = '';
  values.forEach((coefficient, power) => {
    if (coefficient === 0) return;
    const magnitude = Math.abs(coefficient);
    const term = power === 0 ? String(magnitude) : `${magnitude === 1 ? '' : magnitude}${ZETA_POWERS[power]}`;
    if (!text) text = coefficient < 0 ? `-${term}` : term;
    else text += coefficient < 0 ? ` - ${term}` : ` + ${term}`;
  });
  return text || '0';
}

function formatTuple(values: readonly unknown[]): string {
  return `(${values.map((value) => String(value)).join(', ')})`;
}

interface CrossCheck {
  outcome: 'Matches' | 'Differs' | 'Not compared';
  detail: string;
}

const REGISTER_RESULT_PATHS = [['rd_val'], ['rd_value'], ['result', 'rd_val'], ['execution', 'dst'], ['dst']];

function compareRegisterResult(data: ApiRecord, expected: ALHarasRegisterValue): CrossCheck {
  for (const path of REGISTER_RESULT_PATHS) {
    const value = valueAt(data, path);
    if (Array.isArray(value) && value.length === 4 && value.every((item) => typeof item === 'number' || typeof item === 'string')) {
      const where = path.join('.');
      return value.every((item, index) => String(item).trim() === String(expected[index]))
        ? { outcome: 'Matches', detail: `This browser computed ${formatTuple(expected)}; the API returned the same value in ${where}.` }
        : { outcome: 'Differs', detail: `This browser computed ${formatTuple(expected)}; the API returned ${formatTuple(value)} in ${where}.` };
    }
  }
  return {
    outcome: 'Not compared',
    detail: `This browser computed ${formatTuple(expected)}; the response had no four-coefficient register value to compare.`,
  };
}

interface CheckScenario {
  id: string;
  label: string;
  summary: string;
  expected: string;
  request: ApiRecord;
  run: (authToken: string) => Promise<ApiRecord>;
  crossCheck?: (data: ApiRecord) => CrossCheck;
}

interface SecurityCheck {
  id: string;
  title: string;
  question: string;
  computes: string;
  limits: string;
  endpoint: string;
  highlights?: string[][];
  scenarios: [CheckScenario, ...CheckScenario[]];
}

const SECURITY_CHECKS: SecurityCheck[] = [
  {
    id: 'admission',
    title: 'Workload admission decision',
    question: 'Should this workload be admitted, given whether the nodes reporting on it agree, and is that decision signed?',
    computes:
      'Compares the node states exactly, wraps the payload in a Reed–Solomon error-correcting envelope and returns an admit or reject decision signed with Ed25519 and ML-DSA-87.',
    limits: 'Covers only the checks named here; the response lists what it does not check, and the receipt states how the signing key is held.',
    endpoint: 'POST /v1/al-haras/inspect',
    highlights: [
      ['decision', 'decision'],
      ['sheaf_cohomology', 'worst_edge'],
      ['sheaf_cohomology', 'isolating_nodes'],
      ['sheaf_cohomology', 'coboundary_max_edge_norm'],
    ],
    scenarios: [
      {
        id: 'admission-agree',
        label: 'Nodes agree',
        summary: 'Three nodes report the same state (1, 0) for the payload “example-workload-001”; tolerance 0.',
        expected: 'The states are identical, so the API should admit the workload and return a signed decision.',
        request: ADMISSION_AGREE,
        run: (token) => ChronusAPIClient.inspectALHarasWorkload(token, ADMISSION_AGREE),
      },
      {
        id: 'admission-disagree',
        label: 'One node disagrees',
        summary: 'The third node reports (0, 1) while the other two report (1, 0); tolerance 0.',
        expected:
          'The third node disagrees with both of its neighbours, so the API should reject the workload, point to that node and still return a signed decision.',
        request: ADMISSION_DISAGREE,
        run: (token) => ChronusAPIClient.inspectALHarasWorkload(token, ADMISSION_DISAGREE),
      },
    ],
  },
  {
    id: 'agent-consistency',
    title: 'Agent state consistency',
    question: 'Do the agents in a multi-agent pipeline hold consistent state and, if not, which agent is out of line?',
    computes:
      'Compares connected agents’ state vectors in exact arithmetic (a cellular-sheaf coboundary) and reports whether they agree and, if not, where the disagreement lies.',
    limits: 'Agent names and state vectors are example values; no running agents are inspected.',
    endpoint: 'POST /v1/al-haras/applications/agentic-sheaf/verify-turn',
    scenarios: [
      {
        id: 'agents-agree',
        label: 'Agents agree',
        summary: 'Planner, Coder, Executor and Tool each report the state (1, 0, 0, 1).',
        expected: 'No connected pair differs, so the check should report the states as consistent.',
        request: { agent_states: AGENTS_AGREE, stalk_dim: AGENT_STALK_DIM },
        run: (token) => ChronusAPIClient.executeAgenticSheafTurn(token, AGENTS_AGREE, AGENT_STALK_DIM),
      },
      {
        id: 'agents-coder-altered',
        label: 'Coder state altered',
        summary: 'Coder reports (99, -88, 77, 66); the other three agents report (1, 0, 0, 1).',
        expected: 'Only Coder differs, so the check should report disagreement on Coder’s connections and point to Coder.',
        request: { agent_states: AGENTS_CODER_ALTERED, stalk_dim: AGENT_STALK_DIM },
        run: (token) => ChronusAPIClient.executeAgenticSheafTurn(token, AGENTS_CODER_ALTERED, AGENT_STALK_DIM),
      },
    ],
  },
  {
    id: 'mesh-routing',
    title: 'Routing on a modelled mesh',
    question: 'Can a message between two nodes be routed over the modelled mesh, and how well connected is that mesh?',
    computes:
      'Finds a route between two named nodes on a graph model of the mesh and reports it with the graph’s connectivity figures, such as degree and spectral gap; no satellites, radios or live links are involved.',
    limits: 'A graph model only: it says nothing about real links, radio conditions or delivery.',
    endpoint: 'POST /v1/al-haras/applications/orbital-mesh/transmit',
    scenarios: [
      {
        id: 'mesh-route',
        label: 'Route one example packet',
        summary: `Packet “${ROUTE_PACKET}” from node ${ROUTE_SOURCE} to node ${ROUTE_TARGET}; the mesh size is left to the API default.`,
        expected: 'A route between the two nodes should be found and reported with the mesh figures the API computed.',
        request: { packet_payload: ROUTE_PACKET, source_sat: ROUTE_SOURCE, target_sat: ROUTE_TARGET },
        run: (token) => ChronusAPIClient.transmitOrbitalTelemetry(token, ROUTE_PACKET, ROUTE_SOURCE, ROUTE_TARGET),
      },
    ],
  },
  {
    id: 'inference-integrity',
    title: 'Inference integrity re-check',
    question: 'Can a model output be checked against the computation that produced it?',
    computes:
      'Runs a small integer model on the input and re-checks its computation trace with exact finite-field arithmetic; this is not a zero-knowledge proof or a STARK verifier.',
    limits: 'The same API request produces and re-checks the result, so this shows the arithmetic, not independent verification by another party.',
    endpoint: 'POST /v1/al-haras/applications/zk-neural/prove-and-verify',
    scenarios: [
      {
        id: 'inference-example',
        label: 'Example input',
        summary: `Input ${formatTuple(INFERENCE_INPUT)} with the weights label “${INFERENCE_COMMITMENT}”.`,
        expected: 'The re-check of an honestly computed output should hold, and the API should report the output it computed.',
        request: { sensor_input: INFERENCE_INPUT, weights_commitment: INFERENCE_COMMITMENT },
        run: (token) => ChronusAPIClient.executeZkNeuralProveAndVerify(token, INFERENCE_INPUT, INFERENCE_COMMITMENT),
      },
    ],
  },
  {
    id: 'settlement-conservation',
    title: 'Settlement conservation',
    question: 'Does a transfer conserve value, and is a second spend of the same funds refused?',
    computes:
      'Applies the transfer to a model ledger and checks with integer arithmetic that every debit has a matching credit; the double-spend option replays the same funds so the check can refuse them.',
    limits: 'Participants and amounts are example labels in a model ledger; no bank, payment system or funds are involved.',
    endpoint: 'POST /v1/al-haras/applications/cbdc-settlement/process',
    scenarios: [
      {
        id: 'settlement-single',
        label: 'Single transfer',
        summary: `${SETTLEMENT_SENDER} sends ${SETTLEMENT_AMOUNT} tokens to ${SETTLEMENT_RECEIVER} once.`,
        expected: 'Debits equal credits, so value is conserved and the transfer should be accepted.',
        request: {
          sender_bank: SETTLEMENT_SENDER,
          receiver_bank: SETTLEMENT_RECEIVER,
          amount_tokens: SETTLEMENT_AMOUNT,
          simulate_double_spend: false,
        },
        run: (token) =>
          ChronusAPIClient.processCBDCCrossBorderSettlement(token, SETTLEMENT_SENDER, SETTLEMENT_RECEIVER, SETTLEMENT_AMOUNT, false),
      },
      {
        id: 'settlement-replay',
        label: 'Same funds spent twice',
        summary: `${SETTLEMENT_SENDER} spends the same ${SETTLEMENT_AMOUNT} tokens a second time (double-spend option on).`,
        expected: 'The replayed funds break conservation, so the check should refuse the transfer.',
        request: {
          sender_bank: SETTLEMENT_SENDER,
          receiver_bank: SETTLEMENT_RECEIVER,
          amount_tokens: SETTLEMENT_AMOUNT,
          simulate_double_spend: true,
        },
        run: (token) =>
          ChronusAPIClient.processCBDCCrossBorderSettlement(token, SETTLEMENT_SENDER, SETTLEMENT_RECEIVER, SETTLEMENT_AMOUNT, true),
      },
    ],
  },
  {
    id: 'instruction-model',
    title: 'Instruction-set model',
    question:
      'Does the proposed coprocessor instruction set compute exactly, and does its consistency instruction stop output when two registers disagree?',
    computes:
      'Executes one instruction in a software model of the proposed coprocessor: exact multiplication in Z[ζ₅], or a consistency check that blocks the modelled memory bus when two registers differ.',
    limits: 'Software model only: this demonstration involves no hardware, clock-cycle timing or hardware enforcement.',
    endpoint: 'POST /v1/al-haras/applications/t-isa/execute',
    scenarios: [
      {
        id: 'instruction-multiply',
        label: 'Multiply (funct7 0x02)',
        summary: `rs1 = ${formatTuple(MULTIPLY_RS1)}, i.e. ${formatZeta(MULTIPLY_RS1)}; rs2 = ${formatTuple(MULTIPLY_RS2)}, i.e. ${formatZeta(MULTIPLY_RS2)}; the result goes to register ${TISA_REGISTERS.rd}.`,
        expected: `(${formatZeta(MULTIPLY_RS1)})(${formatZeta(MULTIPLY_RS2)}) = ${formatZeta(MULTIPLY_EXPECTED)} exactly, so rd should hold ${formatTuple(MULTIPLY_EXPECTED)}.`,
        request: { funct7: TISA_MULTIPLY, ...TISA_REGISTERS, rs1_val: MULTIPLY_RS1, rs2_val: MULTIPLY_RS2 },
        run: (token) =>
          ChronusAPIClient.executeTISAMicrocode(
            token,
            TISA_MULTIPLY,
            MULTIPLY_RS1,
            MULTIPLY_RS2,
            TISA_REGISTERS.rs1,
            TISA_REGISTERS.rs2,
            TISA_REGISTERS.rd
          ),
        crossCheck: (data) => compareRegisterResult(data, MULTIPLY_EXPECTED),
      },
      {
        id: 'instruction-consistency',
        label: 'Consistency check, registers differ (funct7 0x03)',
        summary: `rs1 = ${formatTuple(MISMATCH_RS1)} and rs2 = ${formatTuple(MISMATCH_RS2)} should agree but do not.`,
        expected: 'The registers differ, so the model should raise its consistency fault and report the modelled memory bus as blocked.',
        request: { funct7: TISA_CONSISTENCY, ...TISA_REGISTERS, rs1_val: MISMATCH_RS1, rs2_val: MISMATCH_RS2 },
        run: (token) =>
          ChronusAPIClient.executeTISAMicrocode(
            token,
            TISA_CONSISTENCY,
            MISMATCH_RS1,
            MISMATCH_RS2,
            TISA_REGISTERS.rs1,
            TISA_REGISTERS.rs2,
            TISA_REGISTERS.rd
          ),
      },
    ],
  },
];

// Defensive readers: response keys are still being revised, so only keys that are present are rendered.

function isRecord(value: unknown): value is ApiRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asRecord(value: unknown): ApiRecord {
  return isRecord(value) ? value : { response: value };
}

function valueAt(source: unknown, path: readonly string[]): unknown {
  let current: unknown = source;
  for (const key of path) {
    if (!isRecord(current)) return undefined;
    current = current[key];
  }
  return current;
}

function optionalText(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

interface Located {
  path: string;
  value: string;
}

function firstText(source: unknown, keys: readonly string[]): Located | null {
  for (const key of keys) {
    const value = optionalText(valueAt(source, [key]));
    if (value !== null) return { path: key, value };
  }
  return null;
}

function humanize(key: string): string {
  const words = key.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : key;
}

function isPrimitive(value: unknown): value is string | number | boolean | null {
  return value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';
}

function isShortPrimitiveList(value: unknown): boolean {
  return Array.isArray(value) && value.length <= 8 && value.every(isPrimitive);
}

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value === null) return 'null';
  return JSON.stringify(value) ?? String(value);
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [];
}

const STATUS_PATHS = [['status'], ['decision'], ['verdict'], ['outcome'], ['decision', 'status'], ['decision', 'decision'], ['result', 'status'], ['execution', 'status']];

function pickStatus(data: ApiRecord): Located | null {
  for (const path of STATUS_PATHS) {
    const value = valueAt(data, path);
    if (typeof value === 'string' && value.trim()) return { path: path.join('.'), value: value.trim() };
  }
  return null;
}

// Meanings for statuses the current AL HARAS engines compute; anything else is shown verbatim with a neutral note.
const STATUS_MEANINGS: Record<string, string> = {
  ADMITTED: 'The node states agreed, so the API recorded an admit decision and signed it.',
  REJECTED_STATE_DISAGREEMENT: 'The node states disagreed, so the API recorded a reject decision and signed it.',
  CONSISTENT: 'Every connected pair of states agrees within the tolerance.',
  INCONSISTENT_STATES: 'At least one connected pair of states differs by more than the tolerance.',
  INCONSISTENT_STATES_ISOLATED:
    'The states disagree, and every disagreeing connection touches the isolating node or nodes the API lists; without them the rest agree.',
  NO_STATE_SUPPLIED: 'No state vectors were supplied, so nothing was compared.',
  INVALID_STATE_INPUT: 'The state input could not be evaluated; the technical detail shows why.',
  SELF_TEST_PASSED: 'Every self-test returned true when the API recomputed it for this request.',
  SELF_TEST_FAILED: 'At least one self-test returned false when the API recomputed it for this request.',
};

const MEANING_KEYS = ['meaning', 'interpretation', 'explanation'];

interface Meaning {
  text: string;
  fromApi: boolean;
  key: string | null;
}

function statusMeaning(status: string | null, data: ApiRecord): Meaning {
  const reported = firstText(data, MEANING_KEYS);
  if (reported) return { text: reported.value, fromApi: true, key: reported.path };
  if (!status) {
    return { text: 'The response did not include a status. Read the computed values and the technical detail instead.', fromApi: false, key: null };
  }
  const known = STATUS_MEANINGS[status.toUpperCase()];
  if (known) return { text: known, fromApi: false, key: null };
  if (/not[_ ]implemented/i.test(status)) {
    return { text: 'The API reports that this is not implemented, so nothing was computed for it.', fromApi: false, key: null };
  }
  return {
    text: `This page has no description for “${status}”. Compare it with the expected outcome and the computed values below.`,
    fromApi: false,
    key: null,
  };
}

interface ReceiptEvidence {
  path: string;
  algorithm: string | null;
  keyId: string | null;
  keyCustody: string | null;
  bodySha256: string | null;
  signature: string | null;
  /** Second signature carried by AL HARAS receipts (ML-DSA-87), when present. */
  postQuantumAlgorithm: string | null;
  postQuantumSignature: string | null;
  body: ApiRecord | null;
}

function findReceipt(source: unknown, path: string[] = [], depth = 0): ReceiptEvidence | null {
  if (!isRecord(source) || depth > 4) return null;
  const signature: unknown = source.signature;
  const signed = isRecord(signature) ? signature : null;
  if ((signed && ('signature_hex' in signed || 'signature' in signed)) || (typeof signature === 'string' && isRecord(source.body))) {
    return {
      path: path.length > 0 ? path.join('.') : 'response',
      algorithm: optionalText(signed ? signed.algorithm : source.algorithm),
      keyId: optionalText(signed ? signed.key_id : source.key_id),
      keyCustody: optionalText(signed ? signed.key_custody : source.key_custody),
      bodySha256: optionalText(signed ? signed.body_sha256 : source.body_sha256),
      signature: signed ? optionalText(signed.signature_hex) ?? optionalText(signed.signature) : optionalText(signature),
      postQuantumAlgorithm: signed && isRecord(signed.post_quantum) ? optionalText(signed.post_quantum.algorithm) : null,
      postQuantumSignature: signed && isRecord(signed.post_quantum) ? optionalText(signed.post_quantum.signature_hex) : null,
      body: isRecord(source.body) ? source.body : null,
    };
  }
  const keys = Object.keys(source);
  const ordered = [...keys.filter((key) => key.includes('receipt')), ...keys.filter((key) => !key.includes('receipt'))];
  for (const key of ordered) {
    const found = findReceipt(source[key], [...path, key], depth + 1);
    if (found) return found;
  }
  return null;
}

function hexByteLength(value: string): number | null {
  return /^[0-9a-f]+$/i.test(value) && value.length % 2 === 0 ? value.length / 2 : null;
}

function signatureSummary(receipt: ReceiptEvidence | null): string {
  if (!receipt) return 'No signed receipt in this response.';
  if (!receipt.signature) return `A receipt is present at ${receipt.path}, but its signature field is empty.`;
  const size = hexByteLength(receipt.signature);
  const first = `${size === null ? '' : `${size}-byte `}signature`;
  if (receipt.postQuantumSignature) {
    const pqSize = hexByteLength(receipt.postQuantumSignature);
    const second = `${pqSize === null ? '' : `${pqSize}-byte `}${receipt.postQuantumAlgorithm ?? 'second'} signature`;
    return `${receipt.algorithm ?? 'Signatures'}: ${first} and ${second} present at ${receipt.path}. Not verified by this page.`;
  }
  return `${receipt.algorithm ?? 'Signature'}: ${first} present at ${receipt.path}. Not verified by this page.`;
}

const RECORD_ID_KEYS = ['receipt_id', 'ovid_receipt_id', 'settlement_id', 'decision_id', 'record_id', 'proof_id', 'receipt_handle'];
const TIME_KEYS = ['timestamp', 'issued_at', 'signed_at', 'computed_at', 'evaluated_at', 'checked_at', 'generated_at', 'created_at'];

function findInResponseOrReceipt(data: ApiRecord, receipt: ReceiptEvidence | null, keys: readonly string[]): Located | null {
  const fromResponse = firstText(data, keys);
  if (fromResponse) return fromResponse;
  if (!receipt?.body) return null;
  const fromBody = firstText(receipt.body, keys);
  return fromBody ? { path: `${receipt.path}.body.${fromBody.path}`, value: fromBody.value } : null;
}

const NOTE_KEYS = ['scope', 'model', 'label', 'implementation', 'implementation_status', 'method', 'note', 'notes', 'statement', 'disclaimer', 'reason', 'error', 'message', 'summary'];
const LIST_KEYS = ['not_implemented', 'checks_not_performed', 'not_covered', 'limitations', 'assumptions', 'caveats'];
const MAX_VALUE_CHARS = 160;
const MAX_VALUES = 14;

interface ValueEntry {
  key: string;
  label: string;
  text: string;
  shortened: boolean;
}

function toEntry(key: string, label: string, value: unknown): ValueEntry {
  const text = displayValue(value);
  const shortened = text.length > MAX_VALUE_CHARS;
  return { key, label, text: shortened ? `${text.slice(0, MAX_VALUE_CHARS)}…` : text, shortened };
}

function computedValues(data: ApiRecord, highlights: readonly string[][], exclude: ReadonlySet<string>) {
  const entries: ValueEntry[] = [];
  for (const path of highlights) {
    const value = valueAt(data, path);
    if (value !== undefined && (isPrimitive(value) || isShortPrimitiveList(value))) {
      const label = path.map((part, index) => (index === 0 ? humanize(part) : part.replace(/[_-]+/g, ' '))).join(' › ');
      entries.push(toEntry(path.join('.'), label, value));
    }
  }
  let omitted = 0;
  for (const [key, value] of Object.entries(data)) {
    if (exclude.has(key) || NOTE_KEYS.includes(key) || LIST_KEYS.includes(key) || MEANING_KEYS.includes(key)) continue;
    if ((isPrimitive(value) || isShortPrimitiveList(value)) && entries.length < MAX_VALUES) entries.push(toEntry(key, humanize(key), value));
    else omitted += 1;
  }
  return { entries, omitted };
}

/** Lists of what the API says it did not cover, at the top level or one object below it. */
function reportedLists(data: ApiRecord) {
  const containers = [data, ...Object.values(data).filter(isRecord)];
  return LIST_KEYS.flatMap((key) => {
    const items = containers.map((container) => stringList(container[key])).find((list) => list.length > 0);
    return items ? [{ key, items }] : [];
  });
}

type ErrorKind = 'denied' | 'invalid' | 'unavailable' | 'failed';

interface ClassifiedError {
  kind: ErrorKind;
  title: string;
  message: string;
  apiMessage: string;
  payload: unknown;
}

function classifyError(cause: unknown, action: string): ClassifiedError {
  if (cause instanceof ChronusAPIError) {
    const base = { apiMessage: cause.message, payload: cause.payload };
    switch (cause.status) {
      case 401:
        return {
          ...base,
          kind: 'denied',
          title: 'Permission denied (HTTP 401)',
          message: `The API did not accept the bearer token, so it did not ${action}. Check that the token is current and issued for your tenant, then try again.`,
        };
      case 403:
        return {
          ...base,
          kind: 'denied',
          title: 'Permission denied (HTTP 403)',
          message: `The API recognised the token, but this tenant is not permitted to ${action}. Ask your platform operator for access.`,
        };
      case 400:
      case 422:
        return { ...base, kind: 'invalid', title: `Input rejected (HTTP ${cause.status})`, message: 'The API rejected the example input, so nothing was computed.' };
      case 0:
      case 502:
      case 503:
      case 504:
        return {
          ...base,
          kind: 'unavailable',
          title: cause.status === 0 ? 'API unavailable' : `API unavailable (HTTP ${cause.status})`,
          message: 'The connected API could not be reached or is not configured, so nothing was computed. Check the backend connection and try again.',
        };
      case 404:
        return {
          ...base,
          kind: 'failed',
          title: 'Not available (HTTP 404)',
          message: 'The connected API does not provide this endpoint; it may be running a different version.',
        };
      default:
        return { ...base, kind: 'failed', title: `Request failed (HTTP ${cause.status})`, message: 'The API returned an error, so no result is available.' };
    }
  }
  return {
    kind: 'failed',
    title: 'Request failed',
    message: 'The request did not complete, so no result is available.',
    apiMessage: cause instanceof Error ? cause.message : '',
    payload: undefined,
  };
}

interface PillState {
  status: string;
  label?: string;
}

const ERROR_PILL: Record<ErrorKind, PillState> = {
  denied: { status: 'BLOCKED', label: 'Permission denied' },
  invalid: { status: 'REJECTED', label: 'Input rejected' },
  unavailable: { status: 'UNAVAILABLE', label: 'API unavailable' },
  failed: { status: 'FAILED', label: 'Failed' },
};

const PANEL = 'gap-5 border-neutral-800 bg-neutral-900/50 p-5 sm:p-6';
const FOCUS_RING = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300';
const PRIMARY_BUTTON = `inline-flex items-center justify-center gap-2 rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS_RING}`;
const SECONDARY_BUTTON = `inline-flex items-center justify-center gap-2 rounded-lg border border-neutral-700 px-3.5 py-2 text-sm font-medium text-neutral-200 transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS_RING}`;
const SECTION_LABEL = 'text-xs font-semibold uppercase tracking-[0.14em] text-neutral-500';
const PRE = `max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-neutral-800 bg-neutral-950 p-3 font-mono text-[11px] leading-5 text-neutral-300 ${FOCUS_RING}`;

const TIME_FORMAT = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'long' });

function TimeStamp({ iso }: { iso: string }) {
  const date = new Date(iso);
  return (
    <time dateTime={iso} title={iso}>
      {Number.isNaN(date.getTime()) ? iso : TIME_FORMAT.format(date)}
    </time>
  );
}

function Spinner() {
  return <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />;
}

function Field({ label, mono = false, children }: { label: string; mono?: boolean; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className={mono ? 'mt-1 break-all font-mono text-xs leading-5 text-neutral-200' : 'mt-1 text-sm leading-6 text-neutral-200'}>{children}</dd>
    </div>
  );
}

function ErrorPanel({ error, at, children }: { error: ClassifiedError; at: string; children?: React.ReactNode }) {
  const tone = error.kind === 'denied' ? 'border-amber-500/25 bg-amber-500/[0.07] text-amber-100' : 'border-rose-500/25 bg-rose-500/10 text-rose-100';
  return (
    <div role="alert" className={`rounded-lg border p-3.5 text-sm ${tone}`}>
      <p className="font-medium">{error.title}</p>
      <p className="mt-1 leading-6 opacity-90">{error.message}</p>
      {error.apiMessage && error.apiMessage !== error.message && (
        <p className="mt-2 max-h-28 overflow-auto break-words font-mono text-xs opacity-80">API message: {error.apiMessage}</p>
      )}
      <p className="mt-2 text-xs opacity-70">
        Recorded <TimeStamp iso={at} /> by this browser.
      </p>
      {children && <div className="mt-3 flex flex-wrap gap-2">{children}</div>}
    </div>
  );
}

function TechnicalDetail({
  endpoint,
  request,
  requestLabel = 'Request body',
  response,
  responseLabel = 'Response body (raw JSON)',
}: {
  endpoint: string;
  request?: ApiRecord;
  requestLabel?: string;
  response?: unknown;
  responseLabel?: string;
}) {
  return (
    <details className="rounded-lg border border-neutral-800 bg-neutral-950/60 text-xs">
      <summary className={`cursor-pointer select-none rounded-lg px-3 py-2.5 font-medium text-neutral-300 transition hover:text-white ${FOCUS_RING}`}>
        Technical detail
      </summary>
      <div className="space-y-3 border-t border-neutral-800 p-3">
        <p className="text-neutral-500">
          Endpoint <code className="ml-1 break-all font-mono text-neutral-300">{endpoint}</code>
        </p>
        {request && (
          <div className="space-y-1.5">
            <p className="text-neutral-500">{requestLabel}</p>
            <pre tabIndex={0} aria-label={requestLabel} className={PRE}>{JSON.stringify(request, null, 2)}</pre>
          </div>
        )}
        {response !== undefined && response !== null && (
          <div className="space-y-1.5">
            <p className="text-neutral-500">{responseLabel}</p>
            <pre tabIndex={0} aria-label={responseLabel} className={PRE}>{JSON.stringify(response, null, 2)}</pre>
          </div>
        )}
      </div>
    </details>
  );
}

function CheckResult({ check, scenario, data, at }: { check: SecurityCheck; scenario: CheckScenario; data: ApiRecord; at: string }) {
  const status = pickStatus(data);
  const meaning = statusMeaning(status?.value ?? null, data);
  const receipt = findReceipt(data);
  const recordId = findInResponseOrReceipt(data, receipt, RECORD_ID_KEYS);
  const serverTime = findInResponseOrReceipt(data, receipt, TIME_KEYS);
  const exclude = new Set(
    [status?.path, receipt?.path, recordId?.path, serverTime?.path, meaning.key].filter(
      (path): path is string => typeof path === 'string' && !path.includes('.')
    )
  );
  const { entries, omitted } = computedValues(data, check.highlights ?? [], exclude);
  const notes = NOTE_KEYS.flatMap((key) => {
    const text = optionalText(data[key]);
    return text ? [{ key, text }] : [];
  });
  const lists = reportedLists(data);
  const cross = scenario.crossCheck?.(data);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <span>Reported status</span>
        {status ? <StatusPill status={status.value} showDot={false} /> : <span className="text-neutral-300">not reported</span>}
        <span>for “{scenario.label}”</span>
      </div>
      <dl className="grid gap-3">
        <Field label={meaning.fromApi ? 'Meaning (as reported by the API)' : 'Meaning'}>{meaning.text}</Field>
        <Field label="Expected for this example">{scenario.expected}</Field>
        {cross && (
          <Field label="Independent check in this browser">
            <span className="font-medium">{cross.outcome}.</span> {cross.detail}
          </Field>
        )}
      </dl>
      <div>
        <h4 className={SECTION_LABEL}>Evidence</h4>
        <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <Field label="Signed receipt">{signatureSummary(receipt)}</Field>
          {receipt?.keyId && <Field label="Signing key id" mono>{receipt.keyId}</Field>}
          {receipt?.keyCustody && <Field label="Key custody (as reported)">{receipt.keyCustody}</Field>}
          {receipt?.bodySha256 && <Field label="Receipt body SHA-256" mono>{receipt.bodySha256}</Field>}
          {recordId && <Field label={`Record id (${recordId.path})`} mono>{recordId.value}</Field>}
          <Field label="Response received (this browser)">
            <TimeStamp iso={at} />
          </Field>
          {serverTime && <Field label={`Server time (${serverTime.path})`} mono>{serverTime.value}</Field>}
        </dl>
      </div>
      {entries.length > 0 && (
        <div>
          <h4 className={SECTION_LABEL}>Computed values, as returned</h4>
          <dl className="mt-2 grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {entries.map((entry) => (
              <Field key={entry.key} label={entry.label} mono>
                {entry.text}
                {entry.shortened && <span className="ml-1 font-sans text-neutral-500">(shortened; full value in the technical detail)</span>}
              </Field>
            ))}
          </dl>
          {omitted > 0 && (
            <p className="mt-2 text-xs text-neutral-500">
              {omitted} further {omitted === 1 ? 'field is' : 'fields are'} in the technical detail.
            </p>
          )}
        </div>
      )}
      {(notes.length > 0 || lists.length > 0) && (
        <div>
          <h4 className={SECTION_LABEL}>Scope reported by the API</h4>
          <dl className="mt-2 grid gap-3">
            {notes.map((note) => (
              <Field key={note.key} label={humanize(note.key)}>{note.text}</Field>
            ))}
            {lists.map((list) => (
              <Field key={list.key} label={humanize(list.key)}>
                <ul className="list-disc space-y-1 pl-4">
                  {list.items.map((item, index) => (
                    <li key={`${list.key}-${index}`}>{item}</li>
                  ))}
                </ul>
              </Field>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}

type CheckRun =
  | { phase: 'idle' }
  | { phase: 'running'; scenario: CheckScenario }
  | { phase: 'done'; scenario: CheckScenario; data: ApiRecord; at: string }
  | { phase: 'error'; scenario: CheckScenario; error: ClassifiedError; at: string };

function SecurityCheckCard({
  check,
  position,
  total,
  authToken,
  onEditToken,
  onDenied,
}: {
  check: SecurityCheck;
  position: number;
  total: number;
  authToken: string;
  onEditToken: () => void;
  onDenied: (error: ClassifiedError, at: string) => void;
}) {
  const baseId = useId();
  const [scenarioId, setScenarioId] = useState(check.scenarios[0].id);
  const [run, setRun] = useState<CheckRun>({ phase: 'idle' });
  const selected = check.scenarios.find((scenario) => scenario.id === scenarioId) ?? check.scenarios[0];
  const token = authToken.trim();
  const running = run.phase === 'running';
  const hintId = `${baseId}-hint`;

  async function execute(scenario: CheckScenario) {
    if (!token || running) return;
    setRun({ phase: 'running', scenario });
    try {
      const data = await scenario.run(token);
      setRun({ phase: 'done', scenario, data: asRecord(data), at: new Date().toISOString() });
    } catch (cause) {
      const error = classifyError(cause, 'run this check');
      const at = new Date().toISOString();
      setRun({ phase: 'error', scenario, error, at });
      if (error.kind === 'denied') onDenied(error, at);
    }
  }

  const pill: PillState =
    run.phase === 'idle'
      ? { status: 'NOT_RUN', label: 'Not run' }
      : run.phase === 'running'
        ? { status: 'CHECKING', label: 'Running' }
        : run.phase === 'error'
          ? ERROR_PILL[run.error.kind]
          : { status: 'RECEIVED', label: 'Result received' };
  const announcement =
    run.phase === 'running' ? `${check.title}: running on the API.` : run.phase === 'done' ? `${check.title}: result received.` : '';
  const shown = run.phase === 'idle' ? selected : run.scenario;

  return (
    <Card className={`${PANEL} min-w-0`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-neutral-500">
            Check {position} of {total}
          </p>
          <h3 className="mt-1 font-semibold text-white">{check.title}</h3>
        </div>
        <StatusPill status={pill.status} label={pill.label} showDot={false} />
      </div>

      <dl className="grid gap-3">
        <Field label="Security question">{check.question}</Field>
        <Field label="What the API computes">{check.computes}</Field>
        <Field label="Limits of this demonstration">{check.limits}</Field>
      </dl>

      <div className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-950/40 p-3.5">
        {check.scenarios.length > 1 ? (
          <fieldset disabled={running} className="space-y-2">
            <legend className="mb-2 text-xs font-medium text-neutral-400">Example input</legend>
            {check.scenarios.map((scenario) => (
              <label
                key={scenario.id}
                className="flex cursor-pointer gap-3 rounded-lg border border-neutral-800 bg-neutral-950/70 p-3 text-sm transition has-[:checked]:border-blue-400/50 has-[:disabled]:cursor-not-allowed"
              >
                <input
                  type="radio"
                  name={`${baseId}-scenario`}
                  value={scenario.id}
                  checked={scenario.id === selected.id}
                  onChange={() => setScenarioId(scenario.id)}
                  className="mt-1 h-4 w-4 shrink-0 accent-blue-500"
                />
                <span className="min-w-0">
                  <span className="block font-medium text-neutral-100">{scenario.label}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-neutral-400">{scenario.summary}</span>
                </span>
              </label>
            ))}
          </fieldset>
        ) : (
          <div>
            <p className="text-xs font-medium text-neutral-400">Example input</p>
            <p className="mt-1 text-sm font-medium text-neutral-100">{selected.label}</p>
            <p className="mt-0.5 text-xs leading-5 text-neutral-400">{selected.summary}</p>
          </div>
        )}
        <p className="text-xs leading-5 text-neutral-400">
          <span className="text-neutral-500">Expected for this example: </span>
          {selected.expected}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => void execute(selected)}
            disabled={!token || running}
            aria-describedby={token ? undefined : hintId}
            className={PRIMARY_BUTTON}
          >
            {running ? (
              <>
                <Spinner />
                Running…
              </>
            ) : (
              'Run check'
            )}
            <span className="sr-only">: {check.title}</span>
          </button>
          {!token && (
            <p id={hintId} className="text-xs text-neutral-500">
              Enter a bearer token under Access to run this check.
            </p>
          )}
        </div>
      </div>

      <p role="status" className="sr-only">
        {announcement}
      </p>
      <div aria-busy={running}>
        {run.phase === 'idle' && (
          <p className="rounded-lg border border-dashed border-neutral-800 px-4 py-6 text-center text-sm text-neutral-500">
            Not run yet. The reported status, its meaning and the evidence will appear here.
          </p>
        )}
        {run.phase === 'running' && (
          <p className="flex items-center justify-center gap-2 rounded-lg border border-neutral-800 px-4 py-6 text-sm text-neutral-300">
            <Spinner />
            Running “{run.scenario.label}” on the connected API…
          </p>
        )}
        {run.phase === 'error' && (
          <ErrorPanel error={run.error} at={run.at}>
            {run.error.kind === 'denied' && (
              <button type="button" onClick={onEditToken} className={SECONDARY_BUTTON}>
                Update token
              </button>
            )}
            <button type="button" onClick={() => void execute(run.scenario)} disabled={!token} className={SECONDARY_BUTTON}>
              Try again
            </button>
          </ErrorPanel>
        )}
        {run.phase === 'done' && <CheckResult check={check} scenario={run.scenario} data={run.data} at={run.at} />}
      </div>

      <TechnicalDetail
        endpoint={check.endpoint}
        request={shown.request}
        requestLabel={run.phase === 'idle' ? 'Request body that Run check will send' : 'Request body sent'}
        response={run.phase === 'done' ? run.data : run.phase === 'error' ? run.error.payload : undefined}
        responseLabel={run.phase === 'error' ? 'Error response body' : 'Response body (raw JSON)'}
      />
    </Card>
  );
}

type StatusLoad =
  | { phase: 'loading' }
  | { phase: 'done'; data: ApiRecord; at: string }
  | { phase: 'error'; error: ClassifiedError; at: string };

function SelfTestResult({ data, at }: { data: ApiRecord; at: string }) {
  const status = pickStatus(data);
  const meaning = statusMeaning(status?.value ?? null, data);
  const selfTests = isRecord(data.self_tests) ? Object.entries(data.self_tests) : [];
  const trueCount = selfTests.filter(([, value]) => value === true).length;
  const notImplemented = stringList(data.not_implemented);
  const implemented = isRecord(data.implemented_checks) ? Object.entries(data.implemented_checks) : [];
  const custody = optionalText(valueAt(data, ['key_custody', 'custody_mode']));

  return (
    <div className="space-y-5">
      <p className="text-sm leading-6 text-neutral-200">{meaning.text}</p>
      <div className="grid gap-5 lg:grid-cols-2">
        {selfTests.length > 0 && (
          <div className="min-w-0">
            <h4 className={SECTION_LABEL}>
              Self-tests: {trueCount} of {selfTests.length} returned true
            </h4>
            <ul className="mt-2 divide-y divide-neutral-800 rounded-lg border border-neutral-800">
              {selfTests.map(([name, value]) => (
                <li key={name} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
                  <span className="min-w-0 text-neutral-300">{humanize(name)}</span>
                  <span className="shrink-0 font-mono text-neutral-100">{displayValue(value)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {notImplemented.length > 0 && (
          <div className="min-w-0">
            <h4 className={SECTION_LABEL}>Not implemented, as reported by the API</h4>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-neutral-300">
              {notImplemented.map((item, index) => (
                <li key={`not-implemented-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {custody && <Field label="Receipt signing key custody (as reported)">{custody}</Field>}
        <Field label="Response received (this browser)">
          <TimeStamp iso={at} />
        </Field>
      </dl>
      {implemented.length > 0 && (
        <details className="rounded-lg border border-neutral-800 bg-neutral-950/60 text-xs">
          <summary className={`cursor-pointer select-none rounded-lg px-3 py-2.5 font-medium text-neutral-300 transition hover:text-white ${FOCUS_RING}`}>
            What the API reports as implemented
          </summary>
          <dl className="grid gap-3 border-t border-neutral-800 p-3">
            {implemented.map(([name, value]) => (
              <Field key={name} label={humanize(name)} mono={typeof value !== 'string'}>
                {displayValue(value)}
              </Field>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}

function ModuleSelfTestPanel() {
  const [state, setState] = useState<StatusLoad>({ phase: 'loading' });

  const load = useCallback(async () => {
    setState({ phase: 'loading' });
    try {
      const data = await ChronusAPIClient.getALHarasStatus();
      setState({ phase: 'done', data: asRecord(data), at: new Date().toISOString() });
    } catch (cause) {
      setState({ phase: 'error', error: classifyError(cause, 'return the module status'), at: new Date().toISOString() });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const status = state.phase === 'done' ? pickStatus(state.data) : null;
  const pill: PillState =
    state.phase === 'loading'
      ? { status: 'CHECKING', label: 'Running self-tests' }
      : state.phase === 'error'
        ? ERROR_PILL[state.error.kind]
        : status
          ? { status: status.value }
          : { status: 'RECEIVED', label: 'No status reported' };

  return (
    <Card className={PANEL} aria-busy={state.phase === 'loading'}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-white">Module self-test</h3>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-neutral-500">
            What the connected API reports about its AL HARAS engines. Public and read-only, so no token is needed; the API recomputes these exact
            self-tests for each request.
          </p>
        </div>
        <StatusPill status={pill.status} label={pill.label} showDot={false} />
      </div>
      {state.phase === 'loading' && (
        <p className="flex items-center gap-2 text-sm text-neutral-300">
          <Spinner />
          Running self-tests on the connected API…
        </p>
      )}
      {state.phase === 'error' && <ErrorPanel error={state.error} at={state.at} />}
      {state.phase === 'done' && <SelfTestResult data={state.data} at={state.at} />}
      <div>
        <button type="button" onClick={() => void load()} disabled={state.phase === 'loading'} className={SECONDARY_BUTTON}>
          {state.phase === 'loading' ? 'Running…' : state.phase === 'error' ? 'Try again' : 'Run self-tests again'}
        </button>
      </div>
      <TechnicalDetail
        endpoint="GET /v1/al-haras/status"
        response={state.phase === 'done' ? state.data : state.phase === 'error' ? state.error.payload : undefined}
        responseLabel={state.phase === 'error' ? 'Error response body' : 'Response body (raw JSON)'}
      />
    </Card>
  );
}

export default function GovernancePage() {
  const [receiptId, setReceiptId] = useState('');
  const [result, setResult] = useState<VerifyReceiptResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // AL HARAS checks: the bearer token lives only in this component's memory.
  const [authToken, setAuthToken] = useState('');
  const [denial, setDenial] = useState<{ title: string; at: string } | null>(null);
  const tokenInputRef = useRef<HTMLInputElement>(null);
  const tokenFieldId = useId();
  const tokenInputId = `${tokenFieldId}-input`;
  const tokenHelpId = `${tokenFieldId}-help`;
  const tokenEntered = authToken.trim().length > 0;

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setResult(null); setError(''); setBusy(true);
    try { setResult(await ChronusAPIClient.verifyReceipt(receiptId.trim())); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Receipt verification failed.'); }
    finally { setBusy(false); }
  }

  const boolLabel = (value: unknown) => value === true ? 'Yes' : value === false ? 'No' : 'Not reported';

  const focusTokenInput = useCallback(() => tokenInputRef.current?.focus(), []);
  const recordDenial = useCallback((denied: ClassifiedError, at: string) => setDenial({ title: denied.title, at }), []);

  function updateToken(value: string) {
    setAuthToken(value);
    setDenial(null);
  }

  return <div className="space-y-7">
    <header className="space-y-2 border-b border-neutral-800 pb-6">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Trust / Governance</p>
      <h1 className="text-3xl font-semibold tracking-tight text-white">Receipt verification and security checks</h1>
      <p className="max-w-3xl text-sm leading-6 text-neutral-400">
        Verify a Chronus execution receipt, then see what the AL HARAS (HYBA Security) checks compute on fixed example inputs.
        Every result on this page is returned by the connected API for a request made from this page.
      </p>
    </header>

    <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
      <form onSubmit={verify} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="flex-1 space-y-1.5 text-sm text-neutral-300">
          <span>Receipt identifier</span>
          <input
            value={receiptId}
            onChange={(e) => setReceiptId(e.target.value)}
            required
            className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
            placeholder="Paste a receipt ID"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !receiptId.trim()}
          className="rounded-lg bg-blue-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-400 disabled:opacity-50"
        >
          {busy ? 'Verifying…' : 'Verify receipt'}
        </button>
      </form>
      {error && <p role="alert" className="mt-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">{error}</p>}
    </Card>

    {result && <Card className="border-neutral-800 bg-neutral-900/50 p-5 sm:p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-neutral-500">Observed receipt result</p>
          <h2 className="mt-1 font-semibold text-white">Signature verification response</h2>
        </div>
        <StatusPill status={String(result.qualification_status || 'NOT_REPORTED')} label={String(result.qualification_status || 'Not reported')} showDot={false} />
      </div>
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div><dt className="text-xs text-neutral-500">Receipt ID</dt><dd className="mt-1 break-all font-mono text-xs text-neutral-200">{result.receipt_id || receiptId}</dd></div>
        <div><dt className="text-xs text-neutral-500">Ed25519 signature valid</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ed25519_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">ML-DSA verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.ml_dsa_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">STARK quotient verification</dt><dd className="mt-1 text-sm text-neutral-200">{boolLabel(result.stark_quotient_verified)}</dd></div>
        <div><dt className="text-xs text-neutral-500">Release gates evaluated</dt><dd className="mt-1 text-sm text-neutral-200">{typeof result.total_release_gates_evaluated === 'number' ? result.total_release_gates_evaluated : 'Not reported'}</dd></div>
        <div><dt className="text-xs text-neutral-500">Summary</dt><dd className="mt-1 text-sm text-neutral-200">{result.invariant_summary || 'Not reported'}</dd></div>
      </dl>
      <p className="mt-5 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-3 py-2.5 text-xs leading-5 text-amber-100/80">
        This response reports the verifier's result only. It is not an independent assessment of the system that produced the receipt.
      </p>
    </Card>}

    <section aria-labelledby="al-haras-heading" className="space-y-5">
      <div className="space-y-2 border-b border-neutral-800 pb-5">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-300">HYBA Security · AL HARAS</p>
        <h2 id="al-haras-heading" className="text-xl font-semibold tracking-tight text-white">Security check demonstrations</h2>
        <p className="max-w-3xl text-sm leading-6 text-neutral-400">
          Each check sends the fixed example input shown to the connected API, which computes the result for that one request. These are
          demonstrations of mathematical checks run by the API. They are not live telemetry, not monitoring of your systems, not hardware results
          and not an assurance that any system is secure.
        </p>
        <p className="max-w-3xl text-xs leading-5 text-neutral-500">
          How to read a result: the reported status and computed values come from the API; “expected for this example” is what a correct check
          should report for that input; a receipt signature is shown as present or absent and is not verified by this page. This page does not
          store results.
        </p>
      </div>

      <ModuleSelfTestPanel />

      <Card className={PANEL}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-start">
          <div className="min-w-0">
            <h3 className="font-semibold text-white">Access</h3>
            <p className="mt-1 text-xs leading-5 text-neutral-500">
              Running a check sends this token to the API as a bearer credential. Without a valid token the API refuses the request as
              permission denied and computes nothing. The module self-test above is public.
            </p>
          </div>
          <form onSubmit={(event) => event.preventDefault()} className="min-w-0 space-y-2">
            <label htmlFor={tokenInputId} className="block text-sm text-neutral-300">Bearer token</label>
            <input
              id={tokenInputId}
              ref={tokenInputRef}
              type="password"
              value={authToken}
              onChange={(event) => updateToken(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-describedby={tokenHelpId}
              className="w-full rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2.5 text-sm text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20"
            />
            <p id={tokenHelpId} className="text-xs text-neutral-500">Used only for this browser session; not saved by this page.</p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                onClick={() => { updateToken(''); tokenInputRef.current?.focus(); }}
                disabled={!authToken}
                className={SECONDARY_BUTTON}
              >
                Clear token
              </button>
              <p aria-live="polite" className="text-xs text-neutral-400">
                {tokenEntered ? 'Token entered: Run check is available on each check below.' : 'No token entered: Run check stays disabled.'}
              </p>
            </div>
            {denial && (
              <p className="rounded-lg border border-amber-500/25 bg-amber-500/[0.07] px-3 py-2 text-xs leading-5 text-amber-100">
                {denial.title} at <TimeStamp iso={denial.at} />. Update the token, then run the check again.
              </p>
            )}
          </form>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {SECURITY_CHECKS.map((check, index) => (
          <SecurityCheckCard
            key={check.id}
            check={check}
            position={index + 1}
            total={SECURITY_CHECKS.length}
            authToken={authToken}
            onEditToken={focusTokenInput}
            onDenied={recordDenial}
          />
        ))}
      </div>
    </section>
  </div>;
}
