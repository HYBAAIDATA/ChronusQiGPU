/** Absent owners are explicit dependencies, not empty customer data or guessed APIs. */
export const INTEGRATIONS = [
  {
    id: "identity",
    owner: "Enterprise identity / AL HARAS",
    capability: "Organisation membership, SSO and role administration",
    needs:
      "Approved IdP metadata, session and membership contracts, permission matrix and test identities.",
  },
  {
    id: "projects",
    owner: "Customer workspace service",
    capability: "Shared workspaces, projects and team permissions",
    needs:
      "Authoritative entity API, retention policy and project-access checks.",
  },
  {
    id: "provisioning",
    owner: "Capacity control plane",
    capability: "Instance allocation and customer lifecycle",
    needs:
      "Resource definition, inventory and recoverable allocation API with approved contract references.",
  },
  {
    id: "metering",
    owner: "Execution metering authority",
    capability: "Authoritative usage facts and durable delivery",
    needs:
      "Measurement semantics, event ownership, durable outbox/ingestion and reconciliation contract.",
  },
  {
    id: "billing",
    owner: "Hermitten",
    capability: "Rating, invoice references and reconciliation",
    needs:
      "Actual source repository or versioned API, sandbox access and approved contract/rate schedules.",
  },
  {
    id: "custody",
    owner: "Theseus service / deployment operator",
    capability: "Enterprise execution retention and restart recovery",
    needs:
      "Approved durable store binding, tenant policy, retention and recovery qualification.",
  },
  {
    id: "support",
    owner: "Authorised service operations",
    capability: "Incidents, support requests and privileged audit views",
    needs:
      "Permissioned support API, escalation channel, retention and time-bounded access policy.",
  },
] as const;
export type IntegrationId = (typeof INTEGRATIONS)[number]["id"];
export class IntegrationUnavailable extends Error {
  readonly code = "integration_not_configured";
  constructor(public integration: IntegrationId) {
    super(
      `The ${integration} service has no verified integration in this workspace.`,
    );
  }
}
export type IntegrationBoundary = {
  id: IntegrationId;
  availability: "unavailable";
  owner: string;
  reason: string;
  /** Deliberately no fetch: no endpoint, credential or schema has been invented. */
  invoke: () => Promise<never>;
};
export function integrationBoundary(id: IntegrationId): IntegrationBoundary {
  const spec = INTEGRATIONS.find((i) => i.id === id)!;
  return {
    id,
    availability: "unavailable",
    owner: spec.owner,
    reason: spec.needs,
    invoke: async () => {
      throw new IntegrationUnavailable(id);
    },
  };
}
