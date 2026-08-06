/**
 * Íconos de redes sociales propios, en SVG estilo lucide (stroke).
 * Las versiones nuevas de lucide-react eliminaron los íconos de marcas
 * (Instagram, Facebook, LinkedIn), así que los dibujamos nosotros y no
 * dependemos de la versión de la librería.
 *
 * Los usan la vidriera pública y la pantalla "Mi página".
 */

import type { ComponentType, CSSProperties, ReactNode } from "react";

export type IconoRedProps = { className?: string; style?: CSSProperties };
export type IconoRed = ComponentType<IconoRedProps>;

function svgBase(props: IconoRedProps, children: ReactNode) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={props.className}
      style={props.style}
      aria-hidden
    >
      {children}
    </svg>
  );
}

export function IconoInstagram(props: IconoRedProps) {
  return svgBase(
    props,
    <>
      <rect x="2" y="2" width="20" height="20" rx="5" />
      <circle cx="12" cy="12" r="4.3" />
      <circle cx="17.3" cy="6.7" r="0.6" fill="currentColor" stroke="none" />
    </>,
  );
}

export function IconoFacebook(props: IconoRedProps) {
  return svgBase(
    props,
    <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />,
  );
}

export function IconoLinkedin(props: IconoRedProps) {
  return svgBase(
    props,
    <>
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4v2a6 6 0 0 1 2-2z" />
      <rect x="2" y="9" width="4" height="12" />
      <circle cx="4" cy="4" r="2" />
    </>,
  );
}

export function IconoTiktok(props: IconoRedProps) {
  return svgBase(props, <path d="M9 12a4 4 0 1 0 4 4V4c.6 2.7 2.3 4.4 5 5" />);
}

/**
 * WhatsApp. A diferencia del resto, este va RELLENO (fill) y no con trazo:
 * el glifo del teléfono dentro del globo no se lee a 16-20px dibujado con
 * stroke, que era el problema del MessageCircle genérico que se usaba antes.
 * Hereda currentColor, así que se tiñe con `style={{ color: ... }}` igual que
 * los demás.
 */
export function IconoWhatsApp(props: IconoRedProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      className={props.className}
      style={props.style}
      aria-hidden
    >
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.87 9.87 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 1.82c2.16 0 4.19.84 5.72 2.37a8.03 8.03 0 0 1 2.37 5.72c0 4.46-3.63 8.09-8.1 8.09a8.2 8.2 0 0 1-4.11-1.12l-.29-.17-3.05.8.81-2.98-.19-.31a8.02 8.02 0 0 1-1.23-4.31c0-4.46 3.63-8.09 8.07-8.09Z" />
      <path d="M9.42 7.35c-.18-.42-.38-.42-.55-.43h-.47c-.16 0-.43.06-.65.31-.23.25-.86.84-.86 2.05s.88 2.38 1 2.54c.12.17 1.71 2.73 4.21 3.72 2.08.82 2.5.66 2.96.61.45-.04 1.46-.59 1.66-1.17.21-.58.21-1.07.14-1.17-.06-.11-.23-.17-.47-.29-.25-.12-1.46-.72-1.69-.8-.22-.09-.39-.13-.55.12s-.63.79-.77.96c-.14.16-.28.19-.53.06-.24-.12-1.03-.38-1.97-1.22-.73-.65-1.22-1.45-1.36-1.7-.14-.25-.02-.38.11-.5.11-.11.25-.29.37-.43.12-.14.16-.25.25-.41.08-.17.04-.31-.02-.43-.06-.13-.54-1.35-.76-1.84Z" />
    </svg>
  );
}
