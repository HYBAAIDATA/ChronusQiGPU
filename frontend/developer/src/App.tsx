import {
  Component as ReactComponent,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  COMPONENTS,
  findComponent,
  sourceUrl,
  type Component,
} from "./catalog";
import { resolveRoute } from "./routes";
import { Badge, Notice, ReferenceLink, State } from "./components/Primitives";

function ComponentDetail({ component: c }: { component: Component }) {
  return (
    <>
      <a className="back-link" href="#/">
        ← All components
      </a>
      <header className="page-intro">
        <p className="eyebrow">{c.role}</p>
        <h1>{c.name}</h1>
        <p className="lead">{c.summary}</p>
        <Badge>{c.status}</Badge>
      </header>
      <div className="detail-grid">
        <section>
          <h2>One owner. A clear boundary.</h2>
          <dl className="definition-list">
            <dt>Owns</dt>
            <dd>{c.owns}</dd>
            <dt>Does not own</dt>
            <dd>{c.boundary}</dd>
            <dt>Interface</dt>
            <dd>{c.interface}</dd>
            <dt>Environment</dt>
            <dd>{c.compatibility}</dd>
          </dl>
        </section>
        <aside className="reference-panel">
          <p className="eyebrow">Evaluate deliberately</p>
          <h2>Read the contract first.</h2>
          <p>{c.limitation}</p>
          <h3>Source references</h3>
          {c.references.length ? (
            <>
              <p className="small">
                These pinned GitHub references require repository access. They
                are not public-release download links.
              </p>
              <ul className="link-list">
                {c.references.map((r) => (
                  <li key={r.path}>
                    <ReferenceLink href={sourceUrl(r.path)}>
                      {r.label}
                    </ReferenceLink>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="small">
              No setup or download link is offered before the integration review
              is complete.
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
function Overview() {
  const [query, setQuery] = useState("");
  const results = COMPONENTS.filter((c) =>
    `${c.name} ${c.role} ${c.summary}`
      .toLowerCase()
      .includes(query.toLowerCase().trim()),
  );
  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">HYBA / Developer reference</p>
          <h1>
            Choose the component.
            <br />
            Keep the boundary.
          </h1>
          <p className="lead">
            Tensor mathematics. Heterogeneous execution. Representation
            transformation. Durable custody. An existing MCP interface.
          </p>
          <a className="button" href="#/guide">
            Start with the source <span aria-hidden="true">→</span>
          </a>
        </div>
        <aside className="hero-note">
          <p className="eyebrow">Source before claims</p>
          <h2>A focused developer release.</h2>
          <p>
            Inspect the responsibilities, interfaces and limitations of five
            components. No dashboard stands in for a working integration.
          </p>
          <p className="small">
            Source inspected ≠ installed, tested or supported release.
          </p>
        </aside>
      </section>
      <Notice title="Candidate reference — not a publication announcement">
        <p>
          GitHub references require repository access. Public release
          destinations, installed-artifact qualification and redistribution
          approval are separate gates. This frontend makes no service
          connection.
        </p>
      </Notice>
      <section aria-labelledby="components-title" className="catalog-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">The initial scope</p>
            <h2 id="components-title">
              Five components. Distinct responsibilities.
            </h2>
          </div>
          <label className="search">
            Find a component
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Name or responsibility"
            />
          </label>
        </div>
        <p className="result-count" role="status">
          {results.length} of {COMPONENTS.length} components
        </p>
        {results.length ? (
          <div className="component-list">
            {results.map((c) => (
              <article key={c.id} className="component-row">
                <div className="component-name">
                  <p className="eyebrow">{c.role}</p>
                  <h3>
                    <a href={`#/components/${c.id}`}>{c.name}</a>
                  </h3>
                </div>
                <p>{c.summary}</p>
                <div className="component-action">
                  <Badge>{c.status}</Badge>
                  <a href={`#/components/${c.id}`}>
                    Read {c.name} reference <span aria-hidden="true">→</span>
                  </a>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <h3>No matching components</h3>
            <p>Search by a component name or responsibility.</p>
            <button type="button" onClick={() => setQuery("")}>
              Clear search
            </button>
          </div>
        )}
      </section>
      <section className="composition">
        <p className="eyebrow">Composition without duplication</p>
        <h2>Connect the owners. Do not replace them.</h2>
        <ol>
          <li>
            <strong>Kellogg</strong>
            <span>Mathematics and tensors</span>
          </li>
          <li>
            <strong>Chronus</strong>
            <span>Execution and device evidence</span>
          </li>
          <li>
            <strong>Ovid</strong>
            <span>Representations and lineage</span>
          </li>
          <li>
            <strong>Theseus</strong>
            <span>Durable custody and recovery</span>
          </li>
        </ol>
        <p>
          MCP exposes implemented tools through their existing owners. This
          responsibility map is not a claim that a five-component workflow has
          been qualified.
        </p>
      </section>
    </>
  );
}
function Guide() {
  return (
    <>
      <header className="page-intro">
        <p className="eyebrow">Evaluation guide</p>
        <h1>Begin with a bounded review.</h1>
        <p className="lead">
          Source access, installation, execution and production support are
          different kinds of evidence.
        </p>
      </header>
      <div className="detail-grid">
        <section>
          <ol className="steps">
            <li>
              <h2>Choose the responsibility.</h2>
              <p>
                Use the component reference to decide which owner matches your
                task. Keep transformation distinct from custody, and mathematics
                distinct from device execution.
              </p>
            </li>
            <li>
              <h2>Read the pinned source.</h2>
              <p>
                Follow the component's repository references with authorised
                access. Check its contract, declared domain, dependency versions
                and limitations before attempting installation.
              </p>
            </li>
            <li>
              <h2>Qualify the first use.</h2>
              <p>
                Use the release owner's approved artifact and environment.
                Retain the exact version, installation log, input, actual output
                and test result. A frontend build is not component execution
                evidence.
              </p>
            </li>
          </ol>
        </section>
        <aside className="reference-panel">
          <h2>Installation is not yet qualified here.</h2>
          <p>
            No package-registry command, container image or public release URL
            has been verified by this frontend change, so none is fabricated.
          </p>
          <p>
            Compatibility statements describe the inspected references, not a
            new support commitment.
          </p>
          <h3>License boundaries</h3>
          <p>
            The repository license and component-specific license statements
            differ. Confirm the license shipped with each approved artifact;
            GitHub access is not a redistribution grant.
          </p>
          <a className="reference-link" href="#/">
            Return to the components →
          </a>
        </aside>
      </div>
    </>
  );
}
export class ErrorBoundary extends ReactComponent<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <State
        title="Reference unavailable"
        action={<a href="./">Reload the reference</a>}
      >
        The page could not be rendered. Reload to retry. No service request was
        submitted.
      </State>
    ) : (
      this.props.children
    );
  }
}
export default function App() {
  const [route, setRoute] = useState(() => resolveRoute(window.location.hash));
  const main = useRef<HTMLElement>(null);
  const navigated = useRef(false);
  useEffect(() => {
    const changed = () => {
      // Skip links change the hash too; preserve their native focus behavior.
      if (window.location.hash === "#main") return;
      navigated.current = true;
      setRoute(resolveRoute(window.location.hash));
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const component =
    route.kind === "component" ? findComponent(route.id) : undefined;
  const title =
    component?.name ??
    (route.kind === "guide"
      ? "Evaluation guide"
      : route.kind === "not-found"
        ? "Page not found"
        : "Developer components");
  useEffect(() => {
    document.title = `HYBA — ${title}`;
    if (navigated.current) {
      main.current?.focus();
      window.scrollTo(0, 0);
    }
  }, [title]);
  return (
    <>
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          main.current?.focus();
          main.current?.scrollIntoView();
        }}
      >
        Skip to content
      </a>
      <header className="site-header">
        <div className="shell header-inner">
          <a
            href="#/"
            className="brand"
            aria-label="HYBA developer reference home"
          >
            HYBA<span>Developer reference</span>
          </a>
          <nav aria-label="Primary">
            <a
              href="#/"
              aria-current={route.kind === "overview" ? "page" : undefined}
            >
              Components
            </a>
            <a
              href="#/guide"
              aria-current={route.kind === "guide" ? "page" : undefined}
            >
              Evaluation guide
            </a>
          </nav>
        </div>
      </header>
      <main className="shell" id="main" tabIndex={-1} ref={main}>
        <ErrorBoundary>
          {route.kind === "overview" ? (
            <Overview />
          ) : component ? (
            <ComponentDetail component={component} />
          ) : route.kind === "guide" ? (
            <Guide />
          ) : (
            <State
              title="Page not found"
              action={
                <a className="button" href="#/">
                  Return to components
                </a>
              }
            >
              This address is not part of the developer reference.
            </State>
          )}
        </ErrorBoundary>
      </main>
      <footer className="site-footer">
        <div className="shell">
          <p>
            <strong>HYBA</strong> / Developer reference
          </p>
          <p>
            Candidate reference · source access required · no production-support
            claim
          </p>
        </div>
      </footer>
    </>
  );
}
