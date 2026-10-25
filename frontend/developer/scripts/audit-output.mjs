import { readdir, readFile, lstat } from "node:fs/promises";
import { resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { inspectAsset } from "./output-policy.mjs";
const frontend = fileURLToPath(new URL("../../", import.meta.url));
const root = resolve(frontend, "../dist/developer");
const files = [];
async function visit(dir) {
  for (const name of await readdir(dir)) {
    const path = resolve(dir, name);
    const info = await lstat(path);
    if (info.isSymbolicLink()) throw new Error(`Symlink refused: ${path}`);
    if (info.isDirectory()) await visit(path);
    else {
      const buffer = await readFile(path);
      const rel = relative(root, path);
      inspectAsset(rel, buffer.toString("utf8"));
      files.push({
        path: rel,
        bytes: buffer.length,
        sha256: createHash("sha256").update(buffer).digest("hex"),
      });
    }
  }
}
await visit(root);
if (
  !files.some((f) => f.path === "index.html") ||
  !files.some((f) => f.path.endsWith(".js"))
)
  throw new Error("Missing production entry");
const html = await readFile(resolve(root, "index.html"), "utf8");
if (!html.includes('content="noindex, nofollow"'))
  throw new Error("Candidate indexing boundary missing");
console.log(
  JSON.stringify(
    {
      status: "PASS",
      scope:
        "static-output pattern audit, not repository/history secret certification",
      files,
    },
    null,
    2,
  ),
);
