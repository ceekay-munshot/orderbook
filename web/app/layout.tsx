import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orderbook — Indian order-book intelligence",
  description:
    "A cross-company dashboard of order and contract wins disclosed by Indian listed companies — every order source- and evidence-backed.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased text-slate-900">{children}</body>
    </html>
  );
}
