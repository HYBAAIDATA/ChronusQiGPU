import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium tracking-wide uppercase",
  {
    variants: {
      tone: {
        default: "bg-secondary text-muted-foreground",
        live: "bg-live/15 text-live",
        warn: "bg-warn/15 text-warn",
        danger: "bg-destructive/15 text-destructive",
        paper: "bg-primary/10 text-foreground",
        theoretical: "bg-theoretical/15 text-theoretical",
      },
    },
    defaultVariants: { tone: "default" },
  },
);

export function Badge({
  className,
  tone,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone, className }))} {...props} />;
}
