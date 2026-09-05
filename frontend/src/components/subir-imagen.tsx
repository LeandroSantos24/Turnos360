"use client";

/**
 * Subir una imagen: elegir el archivo, encuadrarla y guardarla.
 *
 * POR QUÉ HAY UN RECORTE Y NO SOLO UN «elegir archivo»
 * ────────────────────────────────────────────────────
 * El logo y la foto de un profesional se muestran SIEMPRE en un círculo
 * cuadrado. Una foto de celular es rectangular y vertical, así que subirla tal
 * cual significa que el sistema elige el encuadre por vos — y casi siempre
 * elige mal: recorta la cara, o deja al profesional en una esquina. El dueño
 * tiene que poder decir qué parte se ve, y con el dedo, no con un editor.
 *
 * La galería es distinta a propósito: esas fotos se ven grandes y completas,
 * así que ahí no se recorta nada y sube lo que quiera.
 *
 * EL RECORTE PASA EN EL NAVEGADOR
 * ───────────────────────────────
 * Lo que viaja al servidor es la imagen YA recortada. Así el que sube ve
 * exactamente lo que va a quedar —no un «después lo ajustamos»— y de paso se
 * mandan menos bytes: se sube el pedazo elegido, no la foto de 12 megapíxeles.
 */

import { useCallback, useRef, useState } from "react";
import Cropper, { Area } from "react-easy-crop";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { subirImagen, Proposito } from "@/lib/subidas-api";

/** Qué forma tiene el recorte de cada uso. `null` = sin recorte. */
const FORMA: Record<Proposito, { aspecto: number | null; redondo: boolean; ayuda: string }> = {
  avatar: { aspecto: 1, redondo: true, ayuda: "Se ve en un círculo. Centrá la cara." },
  logo: { aspecto: 1, redondo: true, ayuda: "Se ve en un círculo, arriba de tu página." },
  portada: { aspecto: 16 / 9, redondo: false, ayuda: "Es la foto grande de arriba de todo." },
  galeria: { aspecto: null, redondo: false, ayuda: "Se sube completa, sin recortar." },
};

/**
 * Recorta con canvas y devuelve el pedazo elegido como archivo.
 *
 * Se dibuja sobre un canvas del tamaño del recorte y se exporta: el resultado
 * son píxeles nuevos, no la foto original con instrucciones de cómo mirarla.
 */
async function recortar(src: string, area: Area, nombre: string): Promise<File> {
  const img = document.createElement("img");
  img.src = src;
  await new Promise((ok, mal) => {
    img.onload = ok;
    img.onerror = mal;
  });

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(area.width);
  canvas.height = Math.round(area.height);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("No se pudo preparar la imagen");
  ctx.drawImage(
    img,
    area.x, area.y, area.width, area.height,
    0, 0, area.width, area.height,
  );

  const blob = await new Promise<Blob | null>((ok) =>
    canvas.toBlob(ok, "image/webp", 0.92),
  );
  if (!blob) throw new Error("No se pudo preparar la imagen");
  return new File([blob], nombre.replace(/\.[^.]+$/, "") + ".webp", {
    type: "image/webp",
  });
}

export function SubirImagen({
  proposito,
  onSubida,
  etiqueta = "Subir foto",
  size = "default",
}: {
  proposito: Proposito;
  /** Recibe la URL pública de la imagen ya guardada. */
  onSubida: (url: string) => void;
  etiqueta?: string;
  size?: "sm" | "default";
}) {
  const forma = FORMA[proposito];
  const input = useRef<HTMLInputElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [nombre, setNombre] = useState("imagen.webp");
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [area, setArea] = useState<Area | null>(null);
  const [subiendo, setSubiendo] = useState(false);

  const alRecortar = useCallback((_: Area, px: Area) => setArea(px), []);

  function elegir(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    // El input se limpia SIEMPRE: si no, elegir el mismo archivo dos veces
    // seguidas no dispara el evento y parece que la app se colgó.
    e.target.value = "";
    if (!f) return;

    if (!f.type.startsWith("image/")) {
      toast.error("Ese archivo no es una imagen");
      return;
    }
    setNombre(f.name);

    // Sin recorte: derecho al servidor.
    if (forma.aspecto === null) {
      subir(f);
      return;
    }
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setSrc(URL.createObjectURL(f));
  }

  async function subir(archivo: File) {
    setSubiendo(true);
    try {
      const { url } = await subirImagen(archivo, proposito);
      onSubida(url);
      toast.success("Imagen guardada");
      cerrar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo subir");
    } finally {
      setSubiendo(false);
    }
  }

  async function confirmar() {
    if (!src || !area) return;
    try {
      subir(await recortar(src, area, nombre));
    } catch {
      toast.error("No se pudo recortar la imagen");
      setSubiendo(false);
    }
  }

  function cerrar() {
    // La URL del objeto se libera a mano: el navegador no la suelta solo y
    // cada foto elegida deja la anterior en memoria.
    if (src) URL.revokeObjectURL(src);
    setSrc(null);
    setArea(null);
  }

  return (
    <>
      <input
        ref={input}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={elegir}
      />
      <Button
        type="button"
        variant="outline"
        size={size}
        disabled={subiendo}
        onClick={() => input.current?.click()}
      >
        {subiendo ? "Subiendo…" : etiqueta}
      </Button>

      {src && (
        <Dialog open onOpenChange={(o) => !o && cerrar()}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Encuadrá la imagen</DialogTitle>
              <DialogDescription>
                {forma.ayuda} Arrastrá para mover y usá la barra para acercar.
              </DialogDescription>
            </DialogHeader>

            <div className="relative h-72 w-full overflow-hidden rounded-xl bg-muted">
              <Cropper
                image={src}
                crop={crop}
                zoom={zoom}
                aspect={forma.aspecto ?? 1}
                cropShape={forma.redondo ? "round" : "rect"}
                showGrid={!forma.redondo}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={alRecortar}
              />
            </div>

            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground">Acercar</span>
              <input
                type="range"
                min={1}
                max={4}
                step={0.05}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="w-full"
              />
            </label>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={cerrar} disabled={subiendo}>
                Cancelar
              </Button>
              <Button onClick={confirmar} disabled={subiendo || !area}>
                {subiendo ? "Guardando…" : "Usar esta foto"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
