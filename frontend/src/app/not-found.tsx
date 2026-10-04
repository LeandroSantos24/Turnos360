import type { Metadata } from "next";
import Link from "next/link";

/**
 * 404 propia. Sin este archivo Next mostraba la suya, en inglés y sin ningún
 * camino de vuelta: el que llegaba por un link viejo o un slug mal escrito
 * (turnos360.com.ar/barberia-la-cueba) quedaba en una pantalla en blanco con
 * "This page could not be found." Next la sirve con status 404 y noindex.
 */

export const metadata: Metadata = {
  title: "Página no encontrada · Turnos360",
  robots: { index: false, follow: false },
};

const TINTA = "#0c1015";
const TINTA_SUAVE = "#4b5566";

export default function NoEncontrada() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-white px-5">
      <div className="max-w-md text-center">
        <p className="text-sm font-semibold" style={{ color: TINTA_SUAVE }}>
          Error 404
        </p>
        <h1
          className="mt-2 text-3xl font-bold tracking-tight md:text-4xl"
          style={{ fontFamily: "var(--fuente-titulos)", color: TINTA }}
        >
          No encontramos esta página
        </h1>
        <p className="mt-3 text-[15px] leading-relaxed" style={{ color: TINTA_SUAVE }}>
          Puede que el link esté mal escrito o que la página ya no exista. Si
          buscabas un negocio para reservar, revisá la dirección que te
          pasaron.
        </p>
        <Link
          href="/"
          className="mt-8 inline-flex h-11 items-center justify-center rounded-full px-6 text-sm font-semibold text-white"
          style={{ background: TINTA }}
        >
          Ir al inicio
        </Link>
      </div>
    </main>
  );
}
