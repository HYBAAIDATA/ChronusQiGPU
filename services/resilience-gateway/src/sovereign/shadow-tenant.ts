export interface TenantEvent {
  tenantId: string;
  type: string;
  payload: Readonly<Record<string, unknown>>;
  shadowOfEventId?: string;
}

export interface ShadowSink {
  append(event: TenantEvent): Promise<void>;
}

export class ShadowTenant {
  private readonly queuedShocks: TenantEvent[] = [];

  constructor(
    readonly tenantId: string,
    readonly sourceTenantId: string,
    private readonly sink: ShadowSink,
  ) {
    if (tenantId === sourceTenantId) {
      throw new Error("shadow and source tenant must differ");
    }
  }

  async mirror(
    productionEvent: TenantEvent & { eventId: string },
  ): Promise<void> {
    if (productionEvent.tenantId !== this.sourceTenantId) {
      throw new Error("cross-tenant mirror denied");
    }
    await this.sink.append({
      tenantId: this.tenantId,
      type: productionEvent.type,
      payload: productionEvent.payload,
      shadowOfEventId: productionEvent.eventId,
    });
  }

  injectShock(type: string, payload: Readonly<Record<string, unknown>>): void {
    this.queuedShocks.push({ tenantId: this.tenantId, type, payload });
  }

  async flushShocks(): Promise<void> {
    for (const shock of this.queuedShocks.splice(0)) {
      await this.sink.append(shock);
    }
  }

  async outboundWrite(): Promise<never> {
    throw new Error("shadow tenant outbound write path is severed");
  }
}