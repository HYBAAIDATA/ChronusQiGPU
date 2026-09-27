/**
 * Job Manager — lifecycle store for the /api/jobs/* endpoints.
 *
 * In-memory job registry with the create -> submit -> share -> accept
 * lifecycle. Method names are snake_case to match the server.ts call
 * surface (the API contract is already fixed).
 */

export type JobStatus = "created" | "submitted" | "shared" | "accepted" | "failed";
export type JobDispatchStatus = "idle" | "running" | "completed" | "failed";

/**
 * Hardware-execution evidence recorded by the dispatch bridge
 * (scripts/job_dispatch.py). Fields mirror its JSON output verbatim —
 * backend/device/kernel_ms are the punch host's own provenance.
 */
export type JobExecution = Record<string, unknown>;

export interface JobRecord {
  job_id: string;
  name: string;
  description: string;
  payload: Record<string, unknown>;
  owner_id: string;
  status: JobStatus;
  submitter_id: string | null;
  shared_with: string[];
  accepted_by: string | null;
  dispatch_status: JobDispatchStatus;
  execution: JobExecution | null;
  created_at: string;
  updated_at: string;
}

export class Job {
  constructor(private readonly record: JobRecord) {}

  get job_id(): string {
    return this.record.job_id;
  }

  get status(): JobStatus {
    return this.record.status;
  }

  to_dict(): JobRecord {
    return {
      ...this.record,
      shared_with: [...this.record.shared_with],
      execution: this.record.execution ? { ...this.record.execution } : null,
    };
  }
}

function newJobId(): string {
  return globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `job-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export class JobManager {
  private jobs = new Map<string, JobRecord>();

  create_job(
    name: string,
    description: string,
    payload: Record<string, unknown>,
    owner_id: string,
  ): Job {
    const now = new Date().toISOString();
    const record: JobRecord = {
      job_id: newJobId(),
      name,
      description,
      payload: payload ?? {},
      owner_id,
      status: "created",
      submitter_id: null,
      shared_with: [],
      accepted_by: null,
      dispatch_status: "idle",
      execution: null,
      created_at: now,
      updated_at: now,
    };
    this.jobs.set(record.job_id, record);
    return new Job(record);
  }

  get_job(job_id: string): Job | null {
    const record = this.jobs.get(job_id);
    return record ? new Job(record) : null;
  }

  list_jobs(limit = 50, offset = 0): Job[] {
    return [...this.jobs.values()]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(offset, offset + Math.max(0, limit))
      .map((r) => new Job(r));
  }

  search_jobs(query: string, status?: string, owner_id?: string): Job[] {
    const q = (query || "").toLowerCase();
    return [...this.jobs.values()]
      .filter((j) => {
        if (status && j.status !== status) return false;
        if (owner_id && j.owner_id !== owner_id) return false;
        if (!q) return true;
        return (
          j.name.toLowerCase().includes(q) ||
          j.description.toLowerCase().includes(q) ||
          j.job_id.toLowerCase().includes(q)
        );
      })
      .map((r) => new Job(r));
  }

  submit_job(job_id: string, submitter_id: string): Job | null {
    return this._update(job_id, (r) => {
      r.status = "submitted";
      r.submitter_id = submitter_id;
      r.dispatch_status = "running";
    });
  }

  /**
   * Persist hardware-execution evidence from the dispatch bridge.
   * ok evidence -> dispatch_status "completed"; !ok -> "failed" and the
   * job status flips to "failed" (loud, never silently resubmitted).
   */
  record_execution(job_id: string, execution: JobExecution): Job | null {
    return this._update(job_id, (r) => {
      r.execution = { ...execution };
      r.dispatch_status = execution.ok === true ? "completed" : "failed";
      if (execution.ok !== true) r.status = "failed";
    });
  }

  mark_dispatch_failed(job_id: string, error: string): Job | null {
    return this._update(job_id, (r) => {
      r.dispatch_status = "failed";
      r.status = "failed";
      r.execution = { ok: false, error };
    });
  }

  share_job(job_id: string, share_with: string[], _sharer_id: string): Job | null {
    return this._update(job_id, (r) => {
      for (const uid of share_with) {
        if (typeof uid === "string" && !r.shared_with.includes(uid)) {
          r.shared_with.push(uid);
        }
      }
      r.status = "shared";
    });
  }

  accept_job(job_id: string, acceptor_id: string): Job | null {
    return this._update(job_id, (r) => {
      r.status = "accepted";
      r.accepted_by = acceptor_id;
    });
  }

  private _update(job_id: string, mutate: (r: JobRecord) => void): Job | null {
    const record = this.jobs.get(job_id);
    if (!record) return null;
    mutate(record);
    record.updated_at = new Date().toISOString();
    return new Job(record);
  }
}

const _manager = new JobManager();

/** Singleton accessor — matches the server.ts call surface. */
export function get_job_manager(): JobManager {
  return _manager;
}
