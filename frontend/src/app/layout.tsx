import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "@/components/theme-provider";

// PUBLIC_BASE_URL en producción (https://turnos360.com.ar). En desarrollo
// cae a localhost para que las URLs absolutas del Open Graph no rompan.
const BASE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(BASE),
  title: "Turnos360 · Agenda, reservas online y caja para tu negocio",
  description:
    "Los que reservan y no vienen te cuestan plata. Turnos360 cobra la seña online, manda recordatorios y te muestra los números reales de tu barbería, peluquería o salón.",
  keywords: [
    "software de turnos",
    "agenda online barbería",
    "reservas online peluquería",
    "sistema de turnos Argentina",
  ],
  // Lo que se ve cuando el link se comparte por WhatsApp, Instagram o Facebook.
  // Es el canal principal de difusión, así que conviene que se vea bien.
  openGraph: {
    type: "website",
    locale: "es_AR",
    siteName: "Turnos360",
    title: "Turnos360 · Agenda, reservas online y caja para tu negocio",
    description:
      "Reservas 24/7, seña online con Mercado Pago y recordatorios automáticos. Para barberías, peluquerías, salones de uñas y centros de estética.",
    images: [
      {
        url: "/img/duena-notebook.jpg",
        width: 1200,
        height: 800,
        alt: "Turnos360 en uso en un negocio",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Turnos360 · Agenda, reservas online y caja para tu negocio",
    description:
      "Reservas 24/7, seña online con Mercado Pago y recordatorios automáticos para negocios de servicios.",
    images: ["/img/duena-notebook.jpg"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Toaster richColors position="top-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}
