export const privatePatterns = [
  /\b(?:mining|pythia|stratum|mla1517|braiins|viabtc)\b/i,
  /\/api\/(?:auth|v1)/i,
  /(?:VITE_PYTHIA|PYTHIA_API|STRATUM_USER|STRATUM_PASSWORD)/,
  /(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}/,
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /HYBA_PRIVATE_BUILD_CANARY/,
  /sourceMappingURL\s*=/,
];
export function inspectAsset(path, text) {
  if (path.endsWith(".map")) throw new Error(`Source map refused: ${path}`);
  if (!/\.(?:html|js|css|json)$/.test(path))
    throw new Error(`Unreviewed asset type: ${path}`);
  for (const pattern of privatePatterns) {
    if (pattern.test(text))
      throw new Error(
        `Public output policy violation in ${path}: ${pattern.source}`,
      );
  }
}
