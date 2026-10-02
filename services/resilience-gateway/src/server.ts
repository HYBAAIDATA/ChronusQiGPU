import { boot, registerProcessSignals } from "./lifecycle.js";

const runtime = await boot();
registerProcessSignals(runtime);