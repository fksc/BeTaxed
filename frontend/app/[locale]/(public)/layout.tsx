export default function PublicLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="flex min-h-svh flex-1 flex-col">{children}</div>;
}
