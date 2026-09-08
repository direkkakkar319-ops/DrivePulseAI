// Dashboard foundation with explicit empty states until telemetry is connected.
const panels = [
  {
    number: "01",
    title: "Vehicle health",
    description: "Health scores and component insights will appear when vehicle data is available.",
  },
  {
    number: "02",
    title: "Sensor telemetry",
    description: "Explore speed, engine temperature, and battery readings once telemetry is connected.",
  },
  {
    number: "03",
    title: "Maintenance insights",
    description: "Review alerts and the sensor evidence behind each maintenance recommendation.",
  },
];

export default function Home() {
  return (
    <main id="main-content" tabIndex={-1} className="mx-auto max-w-7xl px-6 pb-8 pt-16 sm:px-10 sm:pt-24">
      <section aria-labelledby="overview-title" className="mb-14 max-w-3xl">
        <p className="mb-5 text-xs font-medium uppercase tracking-[0.24em] text-accent">
          Vehicle intelligence
        </p>
        <h1 id="overview-title" className="text-4xl font-medium leading-tight tracking-tight sm:text-6xl">
          A clearer view of<br />
          <span className="text-muted">every journey.</span>
        </h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-muted">
          Your workspace for vehicle health, telemetry, and explainable maintenance insights.
        </p>
      </section>
      <section aria-labelledby="workspace-title">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <h2 id="workspace-title" className="text-lg font-medium">Your dashboard</h2>
          <p className="text-sm text-muted">Awaiting telemetry connection</p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {panels.map((panel) => (
            <article key={panel.number} className="rounded-2xl border border-line bg-panel p-7">
              <span aria-hidden="true" className="text-xs tracking-widest text-accent">{panel.number}</span>
              <h3 className="mb-3 mt-10 text-xl font-medium">{panel.title}</h3>
              <p className="text-sm leading-6 text-muted">{panel.description}</p>
              <p className="mt-8 border-t border-line pt-4 text-xs text-muted">No data yet</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
