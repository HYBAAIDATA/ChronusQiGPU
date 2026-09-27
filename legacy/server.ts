import cors from "cors";
import express, { Express, NextFunction, Request, Response } from "express";
import helmet from "helmet";
import http from "http";
import morgan from "morgan";
import path from "path";

const APP_ROOT = process.cwd();

const app: Express = express();
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || "0.0.0.0";
const NODE_ENV = process.env.NODE_ENV || "development";
const ADMIN_KEY = process.env.EUCLID_ADMIN_API_KEY;
const PYTHIA_PYTHON_API_URL = (
  process.env.PYTHIA_PYTHON_API_URL || "http://localhost:3001"
).replace(/\/$/, "");
const _pyUrl = new URL(PYTHIA_PYTHON_API_URL);
const PYTHIA_API_HOSTNAME = _pyUrl.hostname;
const PYTHIA_API_PORT = parseInt(_pyUrl.port || "3001", 10);
const PYTHON_PROXY_PREFIXES = [
  "/api/v1/",
  "/healthz",
  "/readyz",
  "/ready-to-mine",
  "/api/v1/ready-to-mine",
  "/metrics",
];

function proxyToPythonBackend(req: Request, res: Response): void {
  const options: http.RequestOptions = {
    hostname: PYTHIA_API_HOSTNAME,
    port: PYTHIA_API_PORT,
    path: req.originalUrl,
    method: req.method,
    headers: {
      ...req.headers,
      host: `${PYTHIA_API_HOSTNAME}:${PYTHIA_API_PORT}`,
    },
  };
  const proxy = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode ?? 502, proxyRes.headers);
    proxyRes.pipe(res, { end: true });
  });
  proxy.on("error", () => {
    if (!res.headersSent) {
      res
        .status(502)
        .json({ error: "python_backend_unavailable", backend: PYTHIA_PYTHON_API_URL });
    }
  });
  req.pipe(proxy, { end: true });
}

function miningProxyMiddleware(req: Request, res: Response, next: NextFunction): void {
  const shouldProxy = PYTHON_PROXY_PREFIXES.some(
    (prefix) => req.path === prefix || req.path.startsWith(prefix),
  );
  if (shouldProxy) {
    proxyToPythonBackend(req, res);
    return;
  }
  next();
}

const requireAdminKey = (req: Request, res: Response, next: NextFunction) => {
  const key = req.headers["x-admin-key"] as string | undefined;
  if (!key || key !== ADMIN_KEY) {
    res.status(403).json({ success: false, error: "Unauthorized" });
    return;
  }
  next();
};

app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());
app.use(express.static(path.join(APP_ROOT, "dist", "public")));
app.use(miningProxyMiddleware);

app.get("/api/health", (_req, res) => {
  res.json({ success: true, status: "healthy", timestamp: new Date().toISOString() });
});

app.post("/api/jobs/create", requireAdminKey, async (req, res) => {
  try {
    const { name, description, payload, owner_id = "system" } = req.body || {};
    if (!name || typeof name !== "string") {
      res.status(400).json({ success: false, error: "Job name is required" });
      return;
    }
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const job = jobMgr.create_job(name, description || "", payload || {}, owner_id);
    res.json({ success: true, job: job.to_dict() });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.get("/api/jobs/search", async (req, res) => {
  try {
    const query = (req.query.q as string) || "";
    const status = (req.query.status as string) || undefined;
    const owner_id = (req.query.owner as string) || undefined;
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const jobs = jobMgr.search_jobs(query, status, owner_id);
    res.json({ success: true, count: jobs.length, jobs: jobs.map((job) => job.to_dict()) });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.get("/api/jobs/:job_id", async (req, res) => {
  try {
    const { job_id } = req.params;
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const job = jobMgr.get_job(job_id);
    if (!job) {
      res.status(404).json({ success: false, error: "Job not found" });
      return;
    }
    res.json({ success: true, job: job.to_dict() });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.post("/api/jobs/:job_id/submit", requireAdminKey, async (req, res) => {
  try {
    const { job_id } = req.params;
    const submitter_id = (req.body?.submitter_id as string) || "system";
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const job = jobMgr.submit_job(job_id, submitter_id);
    if (!job) {
      res.status(404).json({ success: false, error: "Job not found" });
      return;
    }
    res.json({ success: true, job: job.to_dict() });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.post("/api/jobs/:job_id/share", requireAdminKey, async (req, res) => {
  try {
    const { job_id } = req.params;
    const { share_with = [], sharer_id = "system" } = req.body || {};
    if (!Array.isArray(share_with)) {
      res.status(400).json({ success: false, error: "share_with must be an array of user IDs" });
      return;
    }
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const job = jobMgr.share_job(job_id, share_with, sharer_id);
    if (!job) {
      res.status(404).json({ success: false, error: "Job not found" });
      return;
    }
    res.json({ success: true, job: job.to_dict() });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.post("/api/jobs/:job_id/accept", requireAdminKey, async (req, res) => {
  try {
    const { job_id } = req.params;
    const acceptor_id = (req.body?.acceptor_id as string) || "system";
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const job = jobMgr.accept_job(job_id, acceptor_id);
    if (!job) {
      res.status(404).json({ success: false, error: "Job not found" });
      return;
    }
    res.json({ success: true, job: job.to_dict() });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.get("/api/jobs", async (req, res) => {
  try {
    const limit = Math.min(Number(req.query.limit) || 50, 200);
    const offset = Number(req.query.offset) || 0;
    const jobManagerModule = await import("./core_engine/job_manager.js");
    const jobMgr = jobManagerModule.get_job_manager();
    const jobs = jobMgr.list_jobs(limit, offset);
    res.json({ success: true, count: jobs.length, jobs: jobs.map((job) => job.to_dict()) });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "unknown_error";
    res.status(500).json({ success: false, error: message });
  }
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(APP_ROOT, "dist", "public", "index.html"));
});

const server = app.listen(PORT, HOST as string, () => {
  console.log(`[EUCLID-CORE] Server running on http://${HOST}:${PORT} (${NODE_ENV})`);
});

server.on("error", (err: NodeJS.ErrnoException) => {
  if (err.code === "EADDRINUSE") {
    console.warn(`[EUCLID-CORE] Port ${PORT} already in use`);
    return;
  }
  console.error("[EUCLID-CORE] Server error", err);
});

const shutdown = (signal: string) => {
  console.log(`[EUCLID-CORE] ${signal} received, shutting down gracefully`);
  server.close(() => {
    console.log("[EUCLID-CORE] HTTP server closed");
    process.exit(0);
  });
};

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
