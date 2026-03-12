import type { Metadata, Viewport } from "next";
import { Navbar } from "@/components/navbar";
import { AuthGate } from "@/components/auth-gate";
import { ServiceWorkerRegistrar } from "@/components/sw-registrar";
import "./globals.css";

export const metadata: Metadata = {
  title: "TheCoach",
  description: "Personal health, longevity & training coach",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "TheCoach",
  },
  icons: {
    icon: "/icon-192.png",
    apple: "/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#059669",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthGate>
          <Navbar />
          <main className="mx-auto max-w-6xl px-4 py-6 pb-20">{children}</main>
        </AuthGate>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}
