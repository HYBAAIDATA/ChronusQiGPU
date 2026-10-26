import React from "react";
export const Empty = () => <span className="console-empty">not reported <span className="sr-only">evidence_status: UNAVAILABLE</span></span>;
export const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => <div className="console-field"><dt>{label}</dt><dd>{children ?? <Empty />}</dd></div>;
export const Alert: React.FC<{ children: React.ReactNode }> = ({ children }) => <div className="console-alert" role="status">{children}</div>;
export const Source: React.FC<{ endpoint: string; timestamp?: string | null }> = ({ endpoint, timestamp }) => <p className="console-source">source: {endpoint} · backend timestamp: {timestamp ?? "not reported"}</p>;
