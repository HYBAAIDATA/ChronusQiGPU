/**
 * Operator kill switch. One cycle halt. Fail-closed.
 * Arm via HYBA_KILL_SWITCH=true or KillSwitch.arm().
 */

export class KillSwitch {
  private static killed = false;
  private static reason: string | null = null;

  static arm(reason: string = "operator"): void {
    this.killed = true;
    this.reason = reason;
  }

  static reset(): void {
    this.killed = false;
    this.reason = null;
  }

  static isKilled(): boolean {
    if (process.env.HYBA_KILL_SWITCH === "true") return true;
    return this.killed;
  }

  static getReason(): string | null {
    if (process.env.HYBA_KILL_SWITCH === "true") return "HYBA_KILL_SWITCH";
    return this.reason;
  }
}
