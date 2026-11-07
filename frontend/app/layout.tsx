import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Plus_Jakarta_Sans } from "next/font/google";
import { AppProvider } from "@/components/AppProvider";
import { ChatWidget } from "@/components/ChatWidget";
import { Footer, Header } from "@/components/Header";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], weight: ["500", "700", "800"], variable: "--font-display" });
const body = Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-body" });

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#1c2551" };

export const metadata: Metadata = {
  title: "KarirFit — Temukan karier yang cocok denganmu",
  description: "Tes gratis yang mencocokkan minat, keterampilan, dan pengalamanmu dengan lowongan kerja di Indonesia, untuk karier IT maupun bidang umum.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className={`${display.variable} ${body.variable}`}>
      <body>
        <AppProvider>
          <Header />
          <main>{children}</main>
          <Footer />
          <ChatWidget />
        </AppProvider>
      </body>
    </html>
  );
}
