"use client";

/**
 * QR de un texto, renderizado como <img> (data URL).
 * Usa la librería `qrcode` (estándar, probada) cargada dinámicamente en el
 * cliente para no tocar el SSR. Nivel de corrección M: aguanta que la tarjeta
 * se manche o se arrugue un poco y sigue leyéndose.
 */

import { useEffect, useState } from "react";

export function CodigoQR({
  texto,
  tam = 200,
  className,
}: {
  texto: string;
  tam?: number;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    import("qrcode")
      .then((QR) =>
        QR.toDataURL(texto, {
          errorCorrectionLevel: "M",
          margin: 2,
          scale: 8,
          color: { dark: "#0c1015", light: "#ffffff" },
        }),
      )
      .then((data) => {
        if (vivo) setUrl(data);
      })
      .catch(() => {
        if (vivo) setUrl(null);
      });
    return () => {
      vivo = false;
    };
  }, [texto]);

  if (!url) {
    return (
      <div
        className={className}
        style={{
          width: tam,
          height: tam,
          background: "#f1f5f9",
          borderRadius: 8,
        }}
        aria-label="Generando QR…"
      />
    );
  }

  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={`QR ${texto}`} width={tam} height={tam} className={className} />;
}
