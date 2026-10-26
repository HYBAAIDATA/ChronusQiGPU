export const SOURCE_REVISION = "b131edc408a37ff7c03534d694bfcdaf0c827abb";
const REPOSITORY = "https://github.com/HYB-APHIDATA/HYBAEnterprise";
export const sourceUrl = (path: string) =>
  `${REPOSITORY}/blob/${SOURCE_REVISION}/${path}`;
export const COMPONENT_IDS = [
  "kellogg",
  "chronus",
  "ovid",
  "theseus",
  "mcp",
] as const;
export type ComponentId = (typeof COMPONENT_IDS)[number];
export type Reference = Readonly<{ label: string; path: string }>;
export type Component = Readonly<{
  id: ComponentId;
  name: string;
  role: string;
  summary: string;
  owns: string;
  boundary: string;
  interface: string;
  compatibility: string;
  limitation: string;
  status: "Source inspected" | "Publication review";
  references: readonly Reference[];
}>;
/** Source-backed responsibilities. Inspection is not installed-artifact qualification. */
export const COMPONENTS: readonly Component[] = [
  {
    id: "kellogg",
    name: "Kellogg",
    role: "Tensor mathematics",
    summary:
      "Define tensor states and mathematical operations with explicit exact and floating-point boundaries.",
    owns: "The tensor system, mathematical operations and their declared invariants.",
    boundary:
      "Device execution belongs to Chronus. Resident tensor blocks are not durable enterprise custody.",
    interface:
      "Python modules under kellogg; the component reference describes exact tensor networks and the separate float plane.",
    compatibility:
      "The component reference lists Python 3.11–3.14 and NumPy. No interpreter or installed distribution was qualified by this frontend build.",
    limitation:
      "The exact path refuses operations outside its declared fields. A source example or certificate is not a production-readiness claim.",
    status: "Source inspected",
    references: [
      {
        label: "Component reference",
        path: "packaging/kellogg-tensor/README.md",
      },
    ],
  },
  {
    id: "chronus",
    name: "Chronus",
    role: "Heterogeneous execution",
    summary:
      "Own the iGPU and heterogeneous execution system, independently of tensor mathematics.",
    owns: "Execution semantics, device routing, memory, kernels and measured execution evidence.",
    boundary:
      "A runtime adapter is not the native architecture. Device presence does not establish that a workload executed.",
    interface:
      "Chronus-1 ISA and kernel ABI are the architecture references; use the declared execution path for the target environment.",
    compatibility:
      "Device, runtime and driver compatibility must be qualified on the intended target. This static reference makes no hardware connection.",
    limitation:
      "No hardware speed, fleet capacity or supported-device claim is inferred from source availability.",
    status: "Source inspected",
    references: [
      { label: "Instruction-set reference", path: "isa/chronus1.md" },
      { label: "Kernel ABI reference", path: "abi/chronus1-abi.md" },
    ],
  },
  {
    id: "ovid",
    name: "Ovid",
    role: "Representation transformation",
    summary:
      "Transform and materialise representations while retaining explicit exactness and transform lineage.",
    owns: "Representation transformation, materialisation, equivalence checks and transform provenance.",
    boundary:
      "Ovid does not provide durable custody or device execution. Producers retain responsibility for the meaning of recovered data.",
    interface:
      "The Python contract names aethel.ovid.open_ovid, metamorphose, materialise and verify_equivalence.",
    compatibility:
      "Use the contract's declared domain and transform version. Byte and numeric transforms have different declared interfaces.",
    limitation:
      "Unknown versions and corrupt forms fail closed. EXACT, BOUNDED_LOSS, APPROXIMATE and UNSUPPORTED are distinct contract classes.",
    status: "Source inspected",
    references: [
      {
        label: "Transformation contract",
        path: "docs/OVID_INTERFACE_CONTRACT.md",
      },
    ],
  },
  {
    id: "theseus",
    name: "Theseus",
    role: "Durable enterprise custody",
    summary:
      "Preserve operational records through integrity checks, recovery and explicit producer revalidation.",
    owns: "Durable custody, integrity, recovery, continuity and custody provenance.",
    boundary:
      "Theseus preserves records; it does not transform representations or decide their semantic validity. Producers revalidate after recovery.",
    interface:
      "The Python contract names aethel.enterprise.custody.compose and EnterpriseCustody, with record, checkpoint and recovery operations.",
    compatibility:
      "Access contracts and persistent storage must be configured by the service owner. The frontend supplies neither credentials nor a custody service.",
    limitation:
      "A stored record is not an access grant. Deployment durability and recovery must be exercised in the supported environment.",
    status: "Source inspected",
    references: [
      { label: "Custody contract", path: "docs/THESEUS_INTERFACE_CONTRACT.md" },
    ],
  },
  {
    id: "mcp",
    name: "MCP integration",
    role: "Existing tool interface",
    summary:
      "Expose the tools implemented by the existing integration, without creating a second computational authority.",
    owns: "The existing hyba_mcp.server identifies itself as hyba-mcp-server and implements a line-oriented JSON-RPC loop over standard input and output.",
    boundary:
      "MCP is an integration surface, not a replacement tensor, execution, transformation or custody system.",
    interface:
      "The inspected server supports initialize, tools/list and tools/call. Its README and implemented tool inventory differ; use implementation evidence during review.",
    compatibility:
      "No browser HTTP transport, hosted endpoint or package-registry installation is asserted here.",
    limitation:
      "The existing server requires a dependency and tool-scope publication review before a public setup command or downloadable integration is offered.",
    status: "Publication review",
    references: [],
  },
];
export function findComponent(id: string): Component | undefined {
  return COMPONENTS.find((component) => component.id === id);
}
