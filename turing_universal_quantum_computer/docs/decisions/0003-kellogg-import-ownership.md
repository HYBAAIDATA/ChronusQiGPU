# ADR 0003 — Keep unrelated consumers out of exact imports

Status: implemented; independently test installed distributions.

Kellogg owns exact mathematics; mining and other systems consume it. Eagerly
importing the canonical mining-oriented tensor surface from `kellogg.__init__`
made an ordinary exact-field import depend on unrelated Chronus modules that
were absent from the installed mathematical package.

Keep those public exports available through the existing lazy attribute resolver,
without copying their implementation or fabricating dependency stubs. Exact
imports no longer initialize that unrelated consumer path. Accessing a lazy
consumer-specific name can still require its legitimate dependencies; this is
not a promise that mining works in a mathematics-only installation.

Regression evidence blocks Chronus imports in fresh processes, checks concurrent
initialization, exercises real exact execution and verifies canonical exports.
Bounded tests do not prove the absence of every circular-import or race scenario.
