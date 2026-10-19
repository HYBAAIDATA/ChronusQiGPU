"use strict";
const $ = (id) => document.getElementById(id);
const surface = location.pathname.slice(1),
  ops = surface === "ops",
  admin = surface === "admin";
let user = null,
  section = ops ? "customers" : admin ? "overview" : "jobs";
const names = {
  overview: "Customer overview",
  customers: "Enterprise customers",
  projects: "Projects and capacity",
  members: "Users and permissions",
  usage: "Usage and costs",
  audit: "Provisioning and audit history",
  jobs: "Computational jobs",
  reconcile: "Service reconciliation",
};
const tenant = () => (ops ? $("target").value.trim() : $("tenant").value);
function message(text, error = false) {
  $("status").textContent = text;
  $("status").className = error ? "error" : "";
}
async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(user?.csrf ? { "X-CSRF-Token": user.csrf } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let value;
  try {
    value = await response.json();
  } catch {
    throw Error("The service returned an invalid response.");
  }
  if (!response.ok) throw Error(value.error || "Service unavailable");
  return value;
}
function element(tag, text) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  return e;
}
function table(rows) {
  const host = $("data");
  host.replaceChildren();
  if (!Array.isArray(rows) || !rows.length) {
    host.append(element("p", "No records are available in this view."));
    return;
  }
  const columns = Object.keys(rows[0]);
  const t = element("table"),
    head = element("thead"),
    tr = element("tr");
  for (const name of columns)
    tr.append(element("th", name.replaceAll("_", " ")));
  if (section === "jobs") tr.append(element("th", "Actions"));
  head.append(tr);
  t.append(head);
  const body = element("tbody");
  for (const row of rows) {
    const r = element("tr");
    for (const col of columns)
      r.append(
        element(
          "td",
          typeof row[col] === "object"
            ? JSON.stringify(row[col])
            : String(row[col] ?? "—"),
        ),
      );
    if (section === "jobs") {
      const cell = element("td");
      const inspect = element("button", "Inspect result");
      inspect.onclick = async () => {
        try {
          const report = await api(
            `/api/customer/${encodeURIComponent(tenant())}/jobs/${encodeURIComponent(row.job)}`,
          );
          host.replaceChildren(element("pre", JSON.stringify(report, null, 2)));
        } catch (error) {
          message(error.message, true);
        }
      };
      cell.append(inspect);
      if (["admitted", "running"].includes(row.state)) {
        const cancel = element("button", "Request cancellation");
        cancel.onclick = async () => {
          try {
            await api(
              `/api/customer/${encodeURIComponent(tenant())}/jobs/${encodeURIComponent(row.job)}/cancel`,
              {},
            );
            message(
              "Cancellation requested; running work remains in flight until fenced.",
            );
            await refresh();
          } catch (error) {
            message(error.message, true);
          }
        };
        cell.append(cancel);
      }
      r.append(cell);
    }
    body.append(r);
  }
  t.append(body);
  if (columns.length > 4 || section === "jobs") t.className = "wide-table";
  host.append(t);
}
function form(fields, submit, label) {
  const f = element("form");
  for (const field of fields) {
    const l = element("label", field.label);
    const input = element(field.area ? "textarea" : "input");
    input.name = field.name;
    input.required = field.required !== false;
    if (!field.area) input.type = field.type || "text";
    if (field.value !== undefined) input.value = field.value;
    if (field.area) l.className = "wide";
    l.append(input);
    f.append(l);
  }
  const b = element("button", label);
  b.type = "submit";
  f.append(b);
  f.onsubmit = async (event) => {
    event.preventDefault();
    b.disabled = true;
    try {
      const data = Object.fromEntries(new FormData(f));
      await submit(data);
      message("Change accepted and recorded.");
      await refresh();
    } catch (error) {
      message(error.message, true);
    } finally {
      b.disabled = false;
    }
  };
  $("actions").append(f);
}
async function refresh() {
  if (!user) return;
  const org = tenant();
  $("sectionTitle").textContent = names[section];
  $("actions").replaceChildren();
  $("data").replaceChildren();
  $("explanation").textContent = "";
  $("metrics").replaceChildren();
  try {
    if (ops) {
      if (section === "customers") {
        const data = user.operator
          ? await api("/api/ops/customers")
          : { customers: [] };
        table(data.customers);
        form(
          [
            {
              name: "action",
              label: "Commercial action (approval, approve, renew, member)",
            },
            {
              name: "payload",
              label: "Approved action payload (JSON, see operations runbook)",
              area: true,
            },
          ],
          (d) => {
            if (!["approval", "approve", "renew", "member"].includes(d.action))
              throw Error("Unsupported commercial action.");
            if (!org) throw Error("Enter a target customer.");
            return api(
              `/api/ops/customers/${encodeURIComponent(org)}/${d.action}`,
              JSON.parse(d.payload),
            );
          },
          "Submit authorised commercial action",
        );
        $("explanation").textContent =
          "First 50 customers. Provisioning changes require approved commercial terms.";
        form(
          [
            { name: "slots", label: "Reserved logical slots", type: "number" },
            { name: "command", label: "Unique change identifier" },
          ],
          (d) => {
            if (!org) throw Error("Enter a target customer.");
            return api(
              `/api/ops/customers/${encodeURIComponent(org)}/provision`,
              { slots: Number(d.slots), command: d.command },
            );
          },
          "Apply reservation",
        );
        form(
          [
            {
              name: "state",
              label: "Lifecycle state (suspended, active, retired)",
            },
            { name: "reason", label: "Authorisation reason" },
            { name: "command", label: "Unique change identifier" },
          ],
          (d) =>
            api(`/api/ops/customers/${encodeURIComponent(org)}/lifecycle`, d),
          "Apply lifecycle change",
        );
      } else {
        const data = await api("/api/ops/reconcile");
        $("data").append(element("pre", JSON.stringify(data, null, 2)));
        const b = element("button", "Deliver pending billing events");
        b.onclick = async () => {
          try {
            const result = await api("/api/ops/billing/deliver", {});
            message(JSON.stringify(result));
          } catch (error) {
            message(error.message, true);
          }
        };
        $("actions").append(b);
      }
      return;
    }
    if (!org)
      throw Error(
        "No active customer membership. Contact your nominated administrator.",
      );
    const base = `/api/customer/${encodeURIComponent(org)}`;
    const overview = await api(base + "/overview");
    for (const [key, label] of [
      ["allocated", "Reserved slots"],
      ["available", "Available slots"],
      ["in_flight", "In-flight jobs"],
      ["consumed", "Verified completions"],
    ]) {
      const box = element("div");
      box.className = "metric";
      box.append(
        element("strong", String(overview[key])),
        element("span", label),
      );
      $("metrics").append(box);
    }
    if (section === "overview") {
      $("data").append(element("pre", JSON.stringify(overview, null, 2)));
      return;
    }
    if (section === "usage") {
      if (admin)
        form(
          [
            {
              name: "amount",
              label: "Expenditure ceiling (decimal, no inferred rate)",
            },
            { name: "currency", label: "ISO currency (e.g. GBP)" },
            { name: "command", label: "Unique change identifier" },
          ],
          (d) => api(base + "/spend-limit", d),
          "Set commercial ceiling",
        );
      table((await api(base + "/usage")).usage);
      try {
        const statement = await api(base + "/billing");
        $("data").append(
          element("h3", "Commercial statement"),
          element("pre", JSON.stringify(statement, null, 2)),
        );
      } catch {
        $("data").append(
          element(
            "p",
            "Commercial statement unavailable. No cost or invoice amount has been inferred.",
          ),
        );
      }
      return;
    }
    const data = await api(base + "/" + section);
    table(data[section]);
    $("explanation").textContent =
      "Up to 50 records. Full cursor-based access is available through the authenticated API.";
    if (
      section === "jobs" &&
      user.memberships.find((m) => m.tenant === org)?.role !== "viewer"
    )
      form(
        [
          { name: "project", label: "Project identifier" },
          { name: "job", label: "Unique job identifier" },
          { name: "shots", label: "Shots", type: "number", value: 128 },
          {
            name: "seed",
            label: "Reproducibility seed",
            type: "number",
            value: 3,
          },
          {
            name: "qasm",
            label: "Admitted Clifford QASM",
            area: true,
            value:
              'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];',
          },
        ],
        (d) =>
          api(base + "/jobs", {
            project: d.project,
            job: d.job,
            request: {
              qasm: d.qasm,
              shots: Number(d.shots),
              seed: Number(d.seed),
            },
          }),
        "Submit governed job",
      );
    if (section === "members")
      form(
        [
          { name: "member", label: "Identity-provider subject" },
          { name: "role", label: "Role (viewer, analyst, admin)" },
          { name: "active", label: "Active (true or false)", value: "true" },
        ],
        (d) => {
          if (!["true", "false"].includes(d.active))
            throw Error("Active must be true or false.");
          return api(base + "/members", { ...d, active: d.active === "true" });
        },
        "Update membership",
      );
    if (admin && section === "projects")
      form(
        [
          { name: "project", label: "Project identifier" },
          { name: "slots", label: "Logical slots", type: "number" },
          { name: "allowance", label: "Completion ceiling", type: "number" },
          { name: "members", label: "Member subjects, comma-separated" },
        ],
        (d) =>
          api(base + "/projects", {
            project: d.project,
            slots: Number(d.slots),
            allowance: Number(d.allowance),
            members: d.members
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
            active: true,
          }),
        "Allocate project capacity",
      );
  } catch (error) {
    message(error.message, true);
  }
}
async function boot() {
  const headings = ops
    ? [
        "Service operations",
        "Privileged provisioning, commercial reconciliation and accountable lifecycle changes.",
      ]
    : admin
      ? [
          "Customer administration",
          "Manage customer access, allocate capacity and review commercial records.",
        ]
      : [
          "Your computational workspace",
          "Submit admitted programs, inspect trusted results and retain provenance.",
        ];
  $("title").textContent = headings[0];
  $("subtitle").textContent = headings[1];
  try {
    user = await api("/api/session");
    if (ops && !user.operator && !user.approver)
      throw Error(
        "A separately authorised service-operations identity is required.",
      );
    $("signin").hidden = true;
    $("app").hidden = false;
    $("logout").hidden = false;
    $("principal").textContent = user.subject;
    $("opsTenant").hidden = !ops;
    $("tenant").parentElement.hidden = ops;
    for (const membership of user.memberships) {
      const option = element("option", membership.tenant);
      option.value = membership.tenant;
      $("tenant").append(option);
    }
    const tabs = ops
      ? ["customers", "reconcile"]
      : admin
        ? ["overview", "projects", "members", "usage", "audit"]
        : ["jobs", "projects"];
    for (const tab of tabs) {
      const b = element("button", names[tab]);
      b.onclick = () => {
        section = tab;
        for (const item of $("tabs").children)
          item.setAttribute("aria-current", String(item === b));
        refresh();
      };
      b.setAttribute("aria-current", String(tab === section));
      $("tabs").append(b);
    }
    $("refresh").onclick = () => {
      message("");
      refresh();
    };
    $("tenant").onchange = refresh;
    $("target").onchange = refresh;
    $("logout").onclick = async () => {
      try {
        await api("/api/logout", {});
        location.reload();
      } catch (error) {
        message(error.message, true);
      }
    };
    await refresh();
  } catch (error) {
    message(error.message, true);
  }
}
boot();
