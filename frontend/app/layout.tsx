import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Turnos360",
  description:
    "SaaS multiempresa de gestión de turnos · CRM · WhatsApp · Finanzas · Fidelización",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
