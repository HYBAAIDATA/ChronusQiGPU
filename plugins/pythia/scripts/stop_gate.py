{"patch":"*** Begin Patch
*** Update File: plugins/pythia/scripts/stop_gate.py
@@
-import hashlib
-import json
-import sys
-from pathlib import Path
-from typing import Any
+import hashlib
+import hmac
+import json
+import os
+import sys
+from pathlib import Path
+from typing import Any
@@
     if claimed != actual:
         return False, "evidence pack SHA256 mismatch"
     if path.stem != claimed:
         return False, "evidence pack filename is not content-addressed by pack SHA256"
+
+    # Owner approval: require an owner HMAC over the pack SHA256 or a recorded
+    # owner_signature. For now we implement HMAC verification using an
+    # environment-provided OWNER_HMAC_KEY. This provides an auditable owner
+    # approval step without adding heavy crypto deps into the runtime.
+    owner_hmac = str(pack.get("owner_hmac") or "").strip()
+    if owner_hmac:
+        key = os.environ.get("OWNER_HMAC_KEY", "").strip()
+        if not key:
+            return False, "owner HMAC key not set in environment (OWNER_HMAC_KEY)"
+        expected = hmac.new(key.encode("utf-8"), actual.encode("utf-8"), hashlib.sha256).hexdigest()
+        if not hmac.compare_digest(owner_hmac, expected):
+            return False, "evidence pack owner HMAC verification failed"
+    else:
+        # No owner_hmac present. Block until an owner approval HMAC is recorded.
+        return False, "evidence pack lacks owner_hmac: owner approval required"
*** End Patch"}