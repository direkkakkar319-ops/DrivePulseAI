// Root layout — shared nav/shell across pages
export const metadata = {
  title: "DrivePulse AI",
  description:
    "Explainable vehicle health digital twin and predictive maintenance platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
