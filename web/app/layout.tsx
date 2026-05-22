import type { Metadata } from "next";
import { Cinzel, EB_Garamond, Italianno } from "next/font/google";
import Nav from "@/components/Nav";
import "./globals.css";

/* ── Display font: Cinzel — engraved Roman capitals ── */
const cinzel = Cinzel({
  variable: "--font-display-var",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  display: "swap",
});

/* ── Body font: EB Garamond — editorial serif ── */
const ebGaramond = EB_Garamond({
  variable: "--font-body-var",
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  display: "swap",
});

/* ── Script accent: Italianno — used sparingly ── */
const italianno = Italianno({
  variable: "--font-script-var",
  subsets: ["latin"],
  weight: ["400"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "FitGraph — AI Outfit Stylist",
  description:
    "Upload a garment and let our graph neural network find perfectly compatible pieces from our catalog.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${cinzel.variable} ${ebGaramond.variable} ${italianno.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-paper text-ink">
        <Nav />
        <div className="flex-1">{children}</div>
      </body>
    </html>
  );
}
