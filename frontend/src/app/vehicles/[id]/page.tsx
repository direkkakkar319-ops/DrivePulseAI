// Per-vehicle detail page
export default function VehicleDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return (
    <main>
      <h1>Vehicle {params.id}</h1>
      <p>Vehicle detail view — coming soon.</p>
    </main>
  );
}
