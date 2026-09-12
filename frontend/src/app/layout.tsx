// Shared document metadata and styles for the product website.
import "../styles/globals.css";
export const metadata = {
  title: "DrivePulse AI — Know your car. Stay ahead.",
  description:
    "Meet DrivePulse AI: an app in development that turns vehicle signals into clear, explainable health and maintenance insights.",
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
