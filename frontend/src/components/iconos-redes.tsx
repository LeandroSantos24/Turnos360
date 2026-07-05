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
