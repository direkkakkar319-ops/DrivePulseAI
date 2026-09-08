// Per-vehicle detail page
import Link from "next/link";

export default function VehicleDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <main id="main-content" tabIndex={-1} className="mx-auto max-w-7xl px-6 py-16 sm:px-10">
      <Link href="/" className="text-sm text-accent hover:underline">Back to overview</Link>
      <h1 className="mt-8 break-words text-3xl font-medium tracking-tight">Vehicle {params.id}</h1>
      <p className="mt-4 text-muted">Vehicle details will appear when telemetry is connected.</p>
    </main>
  );
}
