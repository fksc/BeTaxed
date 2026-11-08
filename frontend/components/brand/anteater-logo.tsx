import { cn } from "@/lib/utils";

const LOCKUP = "/Anteater%20black-screen%20-%20no%20bg.svg";
const MARK = "/Anteater%20no%20text%20icon%20only.svg";

export function AnteaterLogo({
  className,
  collapsedAware = false,
}: {
  className?: string;
  collapsedAware?: boolean;
}) {
  if (!collapsedAware) {
    return (
      <img
        src={LOCKUP}
        alt="Anteater"
        className={cn("h-40 w-auto object-contain", className)}
      />
    );
  }

  return (
    <span className={cn("flex min-w-0 items-center", className)}>
      <img
        src={LOCKUP}
        alt="Anteater"
        className="h-36 w-auto max-w-full object-contain object-left group-data-[collapsible=icon]:hidden"
      />
      <img
        src={MARK}
        alt=""
        className="hidden size-8 object-contain group-data-[collapsible=icon]:block"
      />
    </span>
  );
}

export function AnteaterMark({ className }: { className?: string }) {
  return <img src={MARK} alt="" className={cn("object-contain", className)} />;
}
