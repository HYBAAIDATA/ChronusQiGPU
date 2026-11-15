# Two-run isolation toy model

TLC 1.8.0 (`tla2tools.jar`, SHA-256 `e1f11b75c4b5bc4478ba0ac5cb6ae28e40a01b0016bc33e0aa97da22dfdbcd7f`) on Java 25 was used. From this directory run:

```
java -cp /path/to/tla2tools.jar tlc2.TLC -deadlock -config good.cfg LaneIsolation.tla
java -cp /path/to/tla2tools.jar tlc2.TLC -deadlock -config mutant.cfg LaneIsolation.tla
```

The model compares two two-bit-state executions with the same low input and independently chosen fixed high values. In the good model the low update does not read high. The mutant adds high and must violate the low equality invariant. This is an abstract finite-state illustration only: it is not linked to Chronus RTL, real transient execution, timing, caches, or physical channels. Passing it is not H1.2 acceptance.
