// Product website introducing the planned DrivePulse AI app.
import {
  Activity,
  ArrowDown,
  ArrowUpRight,
  BatteryCharging,
  ChevronRight,
  Cpu,
  Gauge,
  Layers3,
  MoveUpRight,
  ScanLine,
  ShieldCheck,
  Waves,
} from "lucide-react";

import GitHubLink from "../components/GitHubLink";

const features = [
  {
    icon: Activity,
    label: "01 / OBSERVE",
    title: "Every signal.\nOne clear picture.",
    description:
      "Bring temperature, battery, RPM, and vibration together in a digital view of your vehicle’s condition.",
    className: "signal-card",
  },
  {
    icon: ScanLine,
    label: "02 / UNDERSTAND",
    title: "More than an alert.\nThe reason behind it.",
    description:
      "Understand unusual patterns with the sensor evidence behind each insight. Less guesswork, more context.",
    className: "explain-card",
  },
  {
    icon: ShieldCheck,
    label: "03 / PREPARE",
    title: "A little foresight.\nA better next step.",
    description:
      "Explore maintenance risks and clear inspection guidance to make your next conversation with a technician more informed.",
    className: "prepare-card",
  },
];

function PulseMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <Activity size={22} strokeWidth={2.5} />
    </span>
  );
}

function AppPreview() {
  return (
    <div
      className="product-scene"
      aria-label="Illustrative preview of the planned DrivePulse AI mobile app"
    >
      <div className="orbit orbit-one" />
      <div className="orbit orbit-two" />
      <span className="scene-coordinate">CONNECTED INTELLIGENCE / 01</span>
      <div className="floating-note note-top">
        <span className="tiny-icon">
          <ScanLine size={18} />
        </span>
        <div>
          Clarity, built in.<small>Insights with an explanation</small>
        </div>
      </div>
      <div className="phone">
        <div className="phone-camera" />
        <div className="phone-top">
          <span>9:41</span>
          <span>••• ▰</span>
        </div>
        <div className="app-header">
          <PulseMark />
          <span>
            DrivePulse <b>AI</b>
          </span>
          <span className="avatar">D</span>
        </div>
        <div className="app-greeting">YOUR VEHICLE, AT A GLANCE</div>
        <div className="app-title">Ready for what’s ahead.</div>
        <div className="vehicle-label">
          <span className="status-dot" /> SIM-001 <span>Simulated vehicle</span>
        </div>
        <div className="health-ring">
          <div>
            <span>VEHICLE HEALTH</span>
            <strong>
              86<span>/100</span>
            </strong>
            <small>Illustrative score</small>
          </div>
        </div>
        <div className="score-context">
          14 points deducted for an illustrative
          <br />
          battery voltage deviation.
        </div>
        <div className="app-metrics">
          <div>
            <BatteryCharging size={16} />
            <span>Battery</span>
            <strong>
              11.8 <small>V</small>
            </strong>
          </div>
          <div>
            <Gauge size={16} />
            <span>Coolant</span>
            <strong>
              92 <small>°C</small>
            </strong>
          </div>
        </div>
        <div className="app-insight">
          <div>
            <span className="status-dot amber" /> BATTERY INSIGHT{" "}
            <ArrowUpRight size={13} />
          </div>
          <p>Voltage below the reference range.</p>
          <small>Review charging-system readings with a technician.</small>
        </div>
        <div className="app-bottom">
          <Activity size={17} />
          <Layers3 size={17} />
          <ShieldCheck size={17} />
        </div>
        <div className="home-indicator" />
      </div>
      <div className="floating-note note-bottom">
        <span className="tiny-icon">
          <Waves size={18} />
        </span>
        <div>
          See the signal.<small>Understand the story.</small>
        </div>
      </div>
      <span className="preview-caption">APP CONCEPT · SIMULATED DATA</span>
    </div>
  );
}

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="site-header wrap">
        <a href="#" className="brand" aria-label="DrivePulse AI home">
          <PulseMark />
          DrivePulse<span>AI</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#possibilities">The possibilities</a>
          <a href="#how-it-works">How it works</a>
          <a href="#questions">FAQs</a>
        </nav>
        <div className="header-actions">
          <a className="header-cta" href="#the-app">
            Meet the app <ArrowUpRight size={15} />
          </a>
          <GitHubLink />
        </div>
      </header>
      <main id="main-content">
        <section className="hero wrap" aria-labelledby="hero-title">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="status-dot" /> A NEW PERSPECTIVE ON VEHICLE
              HEALTH
            </div>
            <h1 id="hero-title">
              Know your car.
              <br />
              Stay <span>ahead.</span>
            </h1>
            <p>
              Your vehicle has a story to tell. DrivePulse AI is being built to
              turn its signals into clear, explainable maintenance insights. All
              in one app.
            </p>
            <div className="hero-actions">
              <a className="button primary" href="#the-app">
                Discover the app <ArrowUpRight size={18} />
              </a>
              <a className="text-link" href="#how-it-works">
                See how it works <span>↗</span>
              </a>
            </div>
            <div className="hero-footnote">
              <span className="mini-line" /> Designed for clarity. Built around
              you.
            </div>
          </div>
          <AppPreview />
          <a href="#possibilities" className="scroll-cue">
            <ArrowDown size={14} /> EXPLORE WHAT’S POSSIBLE
          </a>
        </section>
        <div className="capability-strip">
          <div className="wrap">
            <span>
              VEHICLE INTELLIGENCE,
              <br />
              <b>WITH A HUMAN SIDE.</b>
            </span>
            <span>
              <Activity /> Sensor awareness
            </span>
            <span>
              <Cpu /> Explainable AI
            </span>
            <span>
              <ShieldCheck /> Maintenance foresight
            </span>
          </div>
        </div>
        <section id="possibilities" className="section wrap">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THE POSSIBILITIES</p>
              <h2>
                Less uncertainty.
                <br />
                <span>More understanding.</span>
              </h2>
            </div>
            <p>
              A warning light is only the beginning.
              <br />
              We’re building a clearer view of what’s happening, why it matters,
              and what to explore next.
            </p>
          </div>
          <div className="feature-grid">
            {features.map(
              ({ icon: Icon, label, title, description, className }) => (
                <article className={`feature-card ${className}`} key={label}>
                  <div className="feature-art" aria-hidden="true">
                    <Icon size={46} strokeWidth={1} />
                    <div className="art-line" />
                    <span>{label.split(" / ")[1]}</span>
                  </div>
                  <p className="eyebrow">{label}</p>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </article>
              ),
            )}
          </div>
        </section>
        <section id="how-it-works" className="process-section">
          <div className="wrap process-layout">
            <div>
              <p className="eyebrow">FROM SIGNAL TO INSIGHT</p>
              <h2>
                Complex under the hood.
                <br />
                <span>Clear in your hands.</span>
              </h2>
              <p className="section-description">
                The planned app connects the dots, so you can focus on the
                bigger picture.
              </p>
              <a className="text-link" href="#the-app">
                Get to know DrivePulse <MoveUpRight size={16} />
              </a>
            </div>
            <div className="steps">
              {[
                [
                  "01",
                  "Observe the signals",
                  "Start with simulated telemetry: battery voltage, temperature, engine load, and more.",
                ],
                [
                  "02",
                  "Find the meaning",
                  "Analyse patterns and maintenance risk, with evidence that makes each insight understandable.",
                ],
                [
                  "03",
                  "Plan the next step",
                  "Bring a clearer picture to a technician with component insights and maintenance reports.",
                ],
              ].map(([number, title, description]) => (
                <article className="step" key={number}>
                  <span>{number}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section id="the-app" className="section wrap">
          <div className="app-banner">
            <div className="banner-art" aria-hidden="true">
              <Activity strokeWidth={0.7} />
              <span className="banner-cross">+</span>
            </div>
            <div className="banner-copy">
              <p className="eyebrow">MEET YOUR NEXT CO-PILOT</p>
              <h2>
                A clearer road
                <br />
                <span>starts here.</span>
              </h2>
              <p>
                Vehicle health. Explained.
                <br />
                DrivePulse AI is currently in development.
              </p>
              <a
                className="button primary"
                href="https://github.com/direkkakkar319-ops/DrivePulseAI"
              >
                Follow the project <ArrowUpRight size={18} />
              </a>
              <small>
                App preview is illustrative. Downloads aren’t available yet.
              </small>
            </div>
          </div>
        </section>
        <section id="questions" className="faq-section wrap">
          <div>
            <p className="eyebrow">A FEW MORE DETAILS</p>
            <h2>
              Good questions.
              <br />
              <span>Clear answers.</span>
            </h2>
          </div>
          <div className="faq-list">
            {[
              [
                "What is DrivePulse AI?",
                "DrivePulse AI is an app in development for explainable vehicle health and predictive maintenance. It aims to bring sensor readings, unusual patterns, and maintenance insights into one understandable view.",
              ],
              [
                "Can I download the app today?",
                "Not yet. This website introduces the product direction. The app is still being developed; you can follow its progress through our GitHub project.",
              ],
              [
                "Does it connect to my car?",
                "The current prototype is being developed with simulated telemetry and public engineering datasets. Direct connection to personal vehicles is not currently available.",
              ],
              [
                "How are the insights explained?",
                "The planned experience shows the readings and contributing factors behind each alert or risk estimate, helping you understand the evidence instead of seeing only a score.",
              ],
              [
                "Does it replace a technician?",
                "No. DrivePulse AI is an educational prototype that provides inspection guidance, not a certified diagnosis. A qualified technician should assess real vehicle concerns.",
              ],
            ].map(([question, answer]) => (
              <details key={question}>
                <summary>
                  {question}
                  <ChevronRight size={18} />
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
      </main>
      <footer className="wrap">
        <div className="footer-top">
          <a href="#" className="brand">
            <PulseMark />
            DrivePulse<span>AI</span>
          </a>
          <p>Intelligence for the road ahead.</p>
          <a href="https://github.com/direkkakkar319-ops/DrivePulseAI">
            GitHub <ArrowUpRight size={14} />
          </a>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} DrivePulse AI</span>
          <span>Independent educational prototype · Simulated data</span>
          <a href="#">Back to top ↑</a>
        </div>
      </footer>
    </>
  );
}
