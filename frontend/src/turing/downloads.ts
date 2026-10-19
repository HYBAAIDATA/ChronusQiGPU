/** Client-only export, with no delivery endpoint, storage or third-party tracking. */
export function downloadJson(value: unknown, suggestedName: string) {
  const filename =
    suggestedName.replace(/[^a-zA-Z0-9_.-]/g, "_").slice(0, 160) ||
    "turing-export.json";
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
