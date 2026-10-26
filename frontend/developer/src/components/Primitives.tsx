import type { ReactNode } from "react";
export function Notice({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <aside className="notice">
      <strong>{title}</strong>
      <div>{children}</div>
    </aside>
  );
}
export function State({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="state">
      <h1>{title}</h1>
      <p>{children}</p>
      {action}
    </section>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}
export function ReferenceLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <a className="reference-link" href={href}>
      {children}
      <span aria-hidden="true"> ↗</span>
    </a>
  );
}
