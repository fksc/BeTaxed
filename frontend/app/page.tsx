import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="flex min-h-full flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">BeTaxed</h1>
      <p className="text-muted-foreground">Frontend skeleton. Product UI comes later.</p>
      <Button type="button" variant="outline" disabled>
        Coming soon
      </Button>
    </main>
  );
}
