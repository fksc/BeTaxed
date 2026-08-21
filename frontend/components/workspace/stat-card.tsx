import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

export function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card className="transition-shadow hover:shadow-sm">
      <CardContent className="p-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs tracking-wider text-muted-foreground uppercase">
            {label}
          </span>
          {icon ? <div className="text-muted-foreground">{icon}</div> : null}
        </div>
        <div className="font-heading text-2xl tracking-tight">{value}</div>
        {hint ? (
          <div className={cn("mt-1.5 text-xs text-muted-foreground")}>{hint}</div>
        ) : null}
      </CardContent>
    </Card>
  );
}
