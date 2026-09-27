import * as SwitchPrimitive from "@radix-ui/react-switch";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

export function Switch(props: ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) {
  const { className, ...rest } = props;
  return (
    <SwitchPrimitive.Root
      className={cn(
        "peer inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-secondary shadow-[var(--shadow-border)] transition-colors data-[state=checked]:bg-primary",
        className,
      )}
      {...rest}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block size-5 translate-x-0.5 rounded-full bg-foreground transition-transform data-[state=checked]:translate-x-[22px] data-[state=checked]:bg-background" />
    </SwitchPrimitive.Root>
  );
}
