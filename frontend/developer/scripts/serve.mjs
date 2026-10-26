import { createServer } from "node:http";
import { readFile, lstat, realpath } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { pathToFileURL } from "node:url";
const root = resolve(
  fileURLToPath(new URL("../../", import.meta.url)),
  "../dist/developer",
);
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};
export function createDeveloperServer() {
  return createServer(async (req, res) => {
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    );
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader("X-Robots-Tag", "noindex, nofollow");
    res.setHeader("Cache-Control", "no-store");
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405, { Allow: "GET, HEAD" });
      res.end();
      return;
    }
    try {
      const pathname = decodeURIComponent(
        new URL(req.url ?? "/", "http://127.0.0.1").pathname,
      );
      if (pathname === "/robots.txt") {
        res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
        res.end(req.method === "HEAD" ? "" : "User-agent: *\nDisallow: /\n");
        return;
      }
      const file = resolve(
        root,
        `.${pathname === "/" ? "/index.html" : pathname}`,
      );
      if (
        !file.startsWith(`${root}${sep}`) ||
        pathname.includes("\\") ||
        pathname.includes("\0") ||
        pathname.split("/").some((p) => p.startsWith("."))
      )
        throw new Error("Not found");
      if (
        file !== resolve(root, "index.html") &&
        !pathname.startsWith("/assets/")
      )
        throw new Error("Not found");
      if (
        !(await lstat(file)).isFile() ||
        !(await realpath(file)).startsWith(`${await realpath(root)}${sep}`)
      )
        throw new Error("Not found");
      const type = types[extname(file)];
      if (!type) throw new Error("Not found");
      const data = await readFile(file);
      res.writeHead(200, {
        "Content-Type": type,
        "Content-Length": data.length,
      });
      res.end(req.method === "HEAD" ? undefined : data);
    } catch {
      res.writeHead(404, { "Content-Type": "text/html; charset=utf-8" });
      res.end(
        req.method === "HEAD"
          ? ""
          : '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HYBA — Page not found</title><h1>Page not found</h1><p>This address is not part of the developer reference.</p><a href="/">Return to components</a></html>',
      );
    }
  });
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const port = Number(process.env.PORT ?? 4173);
  createDeveloperServer().listen(port, "127.0.0.1", () =>
    console.log(`Developer candidate: http://127.0.0.1:${port}`),
  );
}
