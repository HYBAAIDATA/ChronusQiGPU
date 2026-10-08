import React from "react";
import { Cpu, Hexagon, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import type { MlaStatus, ReadyToMine } from "../lib/status";

interface HeaderProps {
  status: MlaStatus | null;
  ready: ReadyToMine | null;
  offline: boolean;
  miningAuthorized?: boolean;
}

const Chip: React.FC<{
  tone: "green" | "amber" | "red" | "dim";
  label: string;
  icon: React.ReactNode;
}> = ({ tone, label, icon }) => (
  <span className="console-surface-inset flex items-center gap-2 px-3 py-1.5 text-[11px] font-telemetry-mono uppercase tracking-wider">
    <span className={`beacon beacon-${tone}`} />
    <span className="text-[#42566f]">{icon}</span>
    <span className="text-[#0a2540]">{label}</span>
  </span>
);

export const Header: React.FC<HeaderProps> = ({
  status,
  ready,
  offline,
  miningAuthorized = true,
}) => {
  const readyToMine = ready?.ready === true;
  const openclDeviceCount = status?.gpu?.opencl_device_count ?? 0;
  const logicalSubstrateAvailable = Boolean(status?.gpu?.logical_substrate?.available);
  const hostBackend = status?.gpu?.logical_substrate?.host_backend ?? "none";
  const contractDeviceName = status?.gpu?.contract_device?.name ?? null;
  const deviceTone = openclDeviceCount > 0
    ? "green"
    : logicalSubstrateAvailable || contractDeviceName
      ? "amber"
      : "dim";
  const deviceLabel = openclDeviceCount > 0
    ? `OpenCL ×${openclDeviceCount}`
    : contractDeviceName
      ? `Chronus · ${contractDeviceName}`
      : logicalSubstrateAvailable
        ? `Super-GPU · ${hostBackend === "cpu" ? "CPU host" : hostBackend}`
        : "no device";

  return (
    <header className="sticky top-0 z-50 border-b border-[rgba(10,37,64,0.13)] bg-[rgba(255,255,255,0.86)] backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 clip-hex bg-[#635bff] text-[#f5f7fa] flex items-center justify-center">
              <Hexagon className="w-5 h-5" strokeWidth={2.4} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-telemetry-mono text-lg font-semibold tracking-[0.22em] uppercase">
                  Pythia
                </span>
                <span className="font-telemetry-mono text-lg font-semibold tracking-[0.22em] uppercase text-[#635bff]">
                  Ops
                </span>
                <span className="hidden md:flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-[2px] bg-[rgba(99,91,255,0.12)] text-[#635bff] font-telemetry-mono uppercase tracking-wider">
                  <ShieldCheck className="w-3 h-3" /> MLA1517 canonical
                </span>
              </div>
              <p className="text-[10px] text-[#6b7c93] font-telemetry-mono uppercase tracking-[0.18em] hidden sm:block">
                Stratum V1 · Python control plane
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!miningAuthorized ? (
              <Chip
                tone="dim"
                label="mining restricted"
                icon={<ShieldCheck className="w-3 h-3" />}
              />
            ) : offline ? (
              <Chip tone="red" label="API offline" icon={<WifiOff className="w-3 h-3" />} />
            ) : (
              <>
                <Chip
                  tone={readyToMine ? "green" : "amber"}
                  label={readyToMine ? "ready to mine" : (ready?.reason ?? "standby")}
                  icon={<Wifi className="w-3 h-3" />}
                />
                <Chip
                  tone={deviceTone}
                  label={deviceLabel}
                  icon={<Cpu className="w-3 h-3" />}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
