import { useEffect, useState, type FormEvent } from "react";
import { INTEGRATIONS } from "./integrations";
import { ARTICLES } from "./productContent";
import type { PublicPage } from "./routes";
import { downloadJson } from "./downloads";
import "./workspace.css";

const SOURCE = "https://github.com/PhiEnterprise1/EuclidPhiEnterprise";
const NAV = [
  ["product", "Product"],
  ["capabilities", "Capabilities"],
  ["enterprise", "Enterprise"],
  ["documentation", "Documentation"],
];
function Enquiry() {
  const [notice, setNotice] = useState("");
  function prepare(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    downloadJson(
      {
        schema_version: "turing.evaluation.enquiry.v1",
        delivery: "local_export_only_not_sent",
        purpose: String(form.get("purpose") ?? ""),
        task: String(form.get("task") ?? "").trim(),
        acceptance_criteria: String(form.get("criteria") ?? "").trim(),
        data_classification: String(form.get("classification") ?? ""),
      },
      "turing-evaluation-enquiry.json",
    );
    setNotice(
      "Evaluation brief downloaded locally. It has not been sent and no enquiry has been opened. Share it through your agreed HYBA contact channel.",
    );
  }
  return (
    <>
      <section className="t-intro">
        <p className="t-eyebrow">Plan a technical evaluation</p>
        <h1>Start with the question that matters.</h1>
        <p>
          Describe the computational task, evidence you need and data
          restrictions. Keep confidential inputs, personal information and
          credentials out of this brief.
        </p>
      </section>
      <div className="t-grid">
        <section className="t-card">
          <h2>Prepare an evaluation brief</h2>
          <p className="t-muted">
            This form creates a local JSON file. No sales, support or CRM
            delivery endpoint has been approved; nothing is sent to HYBA.
          </p>
          <form className="t-form" onSubmit={prepare}>
            <label>
              Engagement type
              <select name="purpose" required>
                <option value="technical_evaluation">
                  Technical evaluation
                </option>
                <option value="enterprise_discussion">
                  Enterprise discussion
                </option>
                <option value="research_partnership">
                  Research partnership
                </option>
              </select>
            </label>
            <label>
              Computational task
              <textarea name="task" required maxLength={2000} rows={4} />
            </label>
            <label>
              What would make the evaluation successful?
              <textarea name="criteria" required maxLength={2000} rows={4} />
            </label>
            <label>
              Intended data classification
              <select name="classification" required>
                <option value="synthetic_or_public">
                  Synthetic or public data only
                </option>
                <option value="requires_review">
                  Confidential data — handling review required first
                </option>
              </select>
            </label>
            <button type="submit">Download evaluation brief</button>
          </form>
          <p role="status" className="t-announcement">
            {notice}
          </p>
        </section>
        <aside className="t-card">
          <p className="t-step">Evaluation sequence</p>
          <h2>Agree. Evaluate. Inspect.</h2>
          <ol className="t-steps">
            <li>Agree a bounded use case and data policy.</li>
            <li>Have the operator issue authorised evaluation access.</li>
            <li>Run supported inputs through the native workflow.</li>
            <li>Inspect results, limitations and evidence together.</li>
            <li>
              Negotiate service arrangements only after capability and
              integration acceptance.
            </li>
          </ol>
          <p className="t-small">
            No automatic account, customer, provisioned instance or commercial
            commitment is created by this form.
          </p>
        </aside>
      </div>
    </>
  );
}
function Home() {
  return (
    <>
      <section className="t-product-hero">
        <div>
          <p className="t-eyebrow">TURING / Computational intelligence</p>
          <h1>
            Precision in.
            <br />
            Evidence out.
          </h1>
          <p className="t-lead">
            A computational workspace for mathematically defined questions—and
            results that can be inspected.
          </p>
          <p className="t-muted">
            Compose native programs. Review before execution. Trace the returned
            result through its validation and provenance.
          </p>
          <div className="t-actions">
            <a className="t-button" href="/turing/app">
              Open evaluation workspace
            </a>
            <a className="t-button t-secondary" href="/turing/how-it-works">
              Understand the workflow
            </a>
          </div>
        </div>
        <aside className="t-journey" aria-label="Computational evidence chain">
          <p className="t-step">The service journey</p>
          <ol>
            <li>
              <span>01 / Mathematical input</span>
              <strong>A precise, bounded program</strong>
              <p>Explicit gates, targets and admission limits.</p>
            </li>
            <li>
              <span>02 / Governed execution</span>
              <strong>The native engine stays in control</strong>
              <p>Authorised request. Validated domain. Real job state.</p>
            </li>
            <li>
              <span>03 / Returned evidence</span>
              <strong>Inspect the result, not just a claim</strong>
              <p>Read validation, configuration and provenance together.</p>
            </li>
          </ol>
        </aside>
      </section>
      <aside className="t-boundary">
        <strong>Technical evaluation. Not a production service.</strong>The
        current implementation retains jobs in one server process. Enterprise
        SSO, durable job custody, capacity provisioning and commercial billing
        are not integrated.
      </aside>
      <section className="t-product-section">
        <p className="t-eyebrow">One coherent working environment</p>
        <h2>For people who need to examine the answer.</h2>
        <div className="t-three">
          <article>
            <span className="t-step">Analysts & researchers</span>
            <h3>Define the task</h3>
            <p>
              Author a native program with visible domain restrictions. Begin
              with an editable Bell-state input, not a precomputed
              demonstration.
            </p>
            <a href="/turing/capabilities">Explore supported capabilities →</a>
          </article>
          <article>
            <span className="t-step">Technical reviewers</span>
            <h3>Interrogate the evidence</h3>
            <p>
              Inspect the original returned report. Distinguish successful
              computation from missing, refused or gated evidence.
            </p>
            <a href="/turing/research">Read the evidence boundary →</a>
          </article>
          <article>
            <span className="t-step">Enterprise evaluators</span>
            <h3>Establish the conditions</h3>
            <p>
              Agree the use case, data handling and acceptance criteria before
              capacity or commercial commitments.
            </p>
            <a href="/turing/enterprise">Plan an enterprise evaluation →</a>
          </article>
        </div>
      </section>
      <section className="t-editorial">
        <div>
          <p className="t-eyebrow">Capability, not theatre</p>
          <h2>
            Mathematical inputs.
            <br />
            Inspectable outcomes.
          </h2>
        </div>
        <div>
          <p>
            TURING is being shaped as computational capability delivered as a
            service—not a chatbot, seat-based software offer or
            physical-hardware onboarding journey.
          </p>
          <p>
            The evaluation workspace exposes a defined slice of the existing
            implementation. It does not imply universal problem-solving,
            unmeasured performance or enterprise service guarantees.
          </p>
          <a href="/turing/documentation">Read the evaluation guide →</a>
        </div>
      </section>
      <section className="t-product-section">
        <h2>Make the first evaluation meaningful.</h2>
        <p className="t-prose">
          Agree a question, execute supported inputs and inspect what the
          service actually returns. Use that evidence to decide what comes next.
        </p>
        <a className="t-button" href="/turing/contact">
          Prepare an evaluation brief
        </a>
      </section>
    </>
  );
}
export default function PublicSite({ page }: { page: PublicPage | null }) {
  const article =
    page && page !== "product" && page !== "contact" ? ARTICLES[page] : null;
  const title =
    article?.title ??
    (page === "product"
      ? "Computational intelligence"
      : page === "contact"
        ? "Plan an evaluation"
        : "Page not found");
  useEffect(() => {
    document.title = `TURING — ${title}`;
  }, [title]);
  return (
    <div className="turing">
      <a className="t-skip" href="#product-content">
        Skip to content
      </a>
      <header className="t-header t-product-header">
        <a className="t-wordmark" href="/turing/product">
          TURING<span>Computational intelligence</span>
        </a>
        <nav className="t-nav" aria-label="Product navigation">
          {NAV.map(([path, label]) => (
            <a
              key={path}
              aria-current={page === path ? "page" : undefined}
              href={`/turing/${path}`}
            >
              {label}
            </a>
          ))}
        </nav>
        <a className="t-button t-secondary" href="/turing/app">
          Evaluation workspace
        </a>
      </header>
      <main className="t-main" id="product-content">
        {page === "product" ? (
          <Home />
        ) : page === "contact" ? (
          <Enquiry />
        ) : article ? (
          <>
            <section className="t-intro">
              <p className="t-eyebrow">{article.eyebrow}</p>
              <h1>{article.title}</h1>
              <p>{article.intro}</p>
            </section>
            <div className="t-article-layout">
              <nav className="t-section-nav" aria-label="On this page">
                {article.sections.map((s, i) => (
                  <a key={s.title} href={`#section-${i + 1}`}>
                    {s.title}
                  </a>
                ))}
              </nav>
              <div className="t-prose">
                {article.sections.map((s, i) => (
                  <section
                    className="t-article-section"
                    id={`section-${i + 1}`}
                    key={s.title}
                  >
                    <h2>{s.title}</h2>
                    {s.paragraphs.map((p) => (
                      <p key={p}>{p}</p>
                    ))}
                    {s.items && (
                      <ul>
                        {s.items.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </section>
                ))}
              </div>
            </div>
            {page === "enterprise" && (
              <section
                className="t-product-section"
                aria-labelledby="integration-title"
              >
                <h2 id="integration-title">
                  Integration status, without ambiguity.
                </h2>
                <ul className="t-integration-list">
                  {INTEGRATIONS.map((i) => (
                    <li key={i.id}>
                      <h3>{i.capability}</h3>
                      <p className="t-small">
                        Owner: {i.owner} ·{" "}
                        {i.id === "billing"
                          ? "On hold — outside current scope"
                          : "Not integrated"}
                      </p>
                      <p>{i.needs}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <aside className="t-boundary">
              <strong>Evaluate the supported workflow.</strong>Authorised
              evaluation access is required for execution.{" "}
              <a href="/turing/app">Open the workspace</a> or{" "}
              <a href="/turing/contact">prepare an evaluation brief</a>.
            </aside>
          </>
        ) : (
          <section className="t-intro">
            <p className="t-eyebrow">404 / Not found</p>
            <h1>This route is not implemented.</h1>
            <p>
              No customer data or administrative capability is implied by this
              address.
            </p>
            <a className="t-button" href="/turing/product">
              Return to product overview
            </a>
          </section>
        )}
      </main>
      <footer className="t-footer t-public-footer">
        <div>
          <strong>TURING / HYBA</strong>
          <p>Technical evaluation · Not a production service.</p>
        </div>
        <nav className="t-nav" aria-label="Further information">
          <a href="/turing/security">Security</a>
          <a href="/turing/research">Research</a>
          <a href="/turing/contact">Evaluation enquiry</a>
          <a href="/turing/legal/privacy">Evaluation data notice</a>
          <a href="/turing/legal/terms">Terms approval status</a>
          <a href={`${SOURCE}/pull/98`}>
            Implementation source (repository access required)
          </a>
        </nav>
      </footer>
    </div>
  );
}
