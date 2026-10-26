"use strict";
const $ = (id) => document.getElementById(id);
const surface = location.pathname.slice(1),
  ops = surface === "ops",
  admin = surface === "admin";
let history = { q: "", state: "", project: "", after: "", previous: [] };
let refreshEpoch = 0;
let user = null,
  section = ops ? "customers" : admin ? "overview" : "jobs";
const names = {
  overview: "Customer overview",
  customers: "Enterprise customers",
  projects: "Projects and capacity",
  members: "Users and permissions",
  usage: "Operational usage",
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
        const epoch = refreshEpoch, org = tenant();
        try {
          const report = await api(
            `/api/customer/${encodeURIComponent(tenant())}/jobs/${encodeURIComponent(row.job)}`,
          );
          if (epoch !== refreshEpoch || org !== tenant()) return;
          const download = element("button", "Export returned report JSON");
          download.onclick = () => {
            const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: "application/json"}));
            const link = element("a"); link.href = url; link.download = "turing-report.json";
            link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
          };
          host.replaceChildren(download, element("pre", JSON.stringify(report, null, 2)));
        } catch (error) {
          message(error.message, true);
        }
      };
      cell.append(inspect);
      if (["admitted", "running"].includes(row.state)) {
        const cancel = element("button", "Request cancellation");
        cancel.onclick = async () => {
          if (!window.confirm("Request cancellation of " + row.job + "? Running work may remain in flight until fenced.")) return;
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
  const epoch = ++refreshEpoch;
  const org = tenant();
  async function currentApi(path, body) {
    const value = await api(path, body);
    if (epoch !== refreshEpoch || org !== tenant()) throw Error("stale_view");
    return value;
  }
  $("sectionTitle").textContent = names[section];
  $("actions").replaceChildren();
  $("data").replaceChildren();
  $("explanation").textContent = "";
  $("metrics").replaceChildren();
  try {
    if (ops) {
      if (section === "customers") {
        const data = user.operator
          ? await currentApi("/api/ops/customers")
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
        const data = await currentApi("/api/ops/reconcile");
        $("data").append(element("pre", JSON.stringify(data, null, 2)));
        $("explanation").textContent =
          "Billing is deferred. Retained usage and lifecycle facts are not invoices or charges.";
      }
      return;
    }
    if (!org)
      throw Error(
        "No active customer membership. Contact your nominated administrator.",
      );
    const base = `/api/customer/${encodeURIComponent(org)}`;
    const overview = await currentApi(base + "/overview");
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
      table((await currentApi(base + "/usage")).usage);
      $("explanation").textContent =
        "Operational completion facts only. Contractual usage-based billing is deferred; no chargeable unit, rate or invoice is implied.";
      return;
    }
    if (section === "jobs") {
      const filters = element("form"); filters.setAttribute("aria-label", "Execution history filters");
      for (const [name, label] of [["q", "Search job identifier"], ["state", "State (admitted, running, completed, failed, cancelled, unknown)"], ["project", "Project identifier filter"]]) {
        const wrapper = element("label", label), input = element("input");
        input.name = name; input.value = history[name]; input.maxLength = name === "q" ? 200 : 256;
        wrapper.append(input); filters.append(wrapper);
      }
      const search = element("button", "Apply filters"); search.type = "submit"; filters.append(search);
      filters.onsubmit = event => {
        event.preventDefault(); const values = Object.fromEntries(new FormData(filters));
        history = {...values, after: "", previous: []}; refresh();
      };
      $("actions").append(filters);
    }
    const query = section === "jobs" ? "?" + new URLSearchParams({q: history.q, state: history.state, project: history.project, after: history.after, limit: "50"}) : "";
    const data = await currentApi(base + "/" + section + query);
    table(data[section]);
    if (section === "jobs") {
      const pagination = element("nav"); pagination.setAttribute("aria-label", "Execution history pages");
      const previous = element("button", "Previous page"); previous.disabled = history.previous.length === 0;
      previous.onclick = () => { history.after = history.previous.pop(); refresh(); };
      const next = element("button", "Next page"); next.disabled = !data.next_cursor;
      next.onclick = () => { history.previous.push(history.after); history.after = data.next_cursor; refresh(); };
      pagination.append(previous, next); $("data").append(pagination);
    }
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
    if (error.message !== "stale_view" && epoch === refreshEpoch) message(error.message, true);
  }
}
async function boot() {
  const headings = ops
    ? [
        "Service operations",
        "Privileged provisioning, operational reconciliation and accountable lifecycle changes.",
      ]
    : admin
      ? [
          "Customer administration",
          "Manage customer access, allocate capacity and review operational records.",
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
    $("tenant").onchange = () => { history = {q: "", state: "", project: "", after: "", previous: []}; refresh(); };
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
