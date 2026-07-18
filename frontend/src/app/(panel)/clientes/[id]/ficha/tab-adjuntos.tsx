"use client";

/**
 * Tab "Adjuntos" de la ficha: los documentos del paciente.
 * Como mínimo, los 2 PDF del informe ISAK por historia; además estudios,
 * análisis y el plan nutricional. En esta etapa se cargan por URL
 * (Drive/Cloudinary/etc.); la subida directa de archivos llega post-deploy.
 */

import { useCallback, useEffect, useState } from "react";
import { FileText, ExternalLink, Plus } from "lucide-react";
import { toast } from "sonner";

import {
  listarAdjuntos,
  crearAdjunto,
  borrarAdjunto,
  Adjunto,
} from "@/lib/ficha-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Seccion, BotonBorrar } from "./comunes";

const TIPOS: [string, string][] = [
  ["pdf_isak", "Informe ISAK (PDF)"],
  ["estudio", "Estudio / análisis"],
  ["plan", "Plan nutricional"],
  ["otro", "Otro"],
];

function etiquetaTipo(tipo: string | null): string {
  return TIPOS.find(([v]) => v === tipo)?.[1] ?? "Documento";
}

function fechaHoraLegible(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
}

export function TabAdjuntos({ clienteId }: { clienteId: number }) {
  const [adjuntos, setAdjuntos] = useState<Adjunto[]>([]);
  const [cargando, setCargando] = useState(true);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [nombre, setNombre] = useState("");
  const [url, setUrl] = useState("");
  const [tipo, setTipo] = useState("pdf_isak");
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setAdjuntos(await listarAdjuntos(clienteId));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudieron cargar los adjuntos");
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardar() {
    const n = nombre.trim();
    const u = url.trim();
    if (!n || !u) {
      toast.error("Completá el nombre y la URL del documento");
      return;
    }
    if (!/^https?:\/\//i.test(u)) {
      toast.error("La URL tiene que empezar con http:// o https://");
      return;
    }
    setGuardando(true);
    try {
      await crearAdjunto(clienteId, { nombre_archivo: n, ruta: u, tipo });
      toast.success("Adjunto guardado");
      setNombre("");
      setUrl("");
      setMostrarForm(false);
      cargar();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function borrar(id: number) {
    try {
      await borrarAdjunto(clienteId, id);
      setAdjuntos((lista) => lista.filter((a) => a.id !== id));
      toast.success("Adjunto borrado");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo borrar");
    }
  }

  return (
    <div className="space-y-6">
      {!mostrarForm ? (
        <Button onClick={() => setMostrarForm(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> Nuevo adjunto
        </Button>
      ) : (
        <Seccion titulo="Nuevo adjunto">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Nombre del documento</Label>
              <Input
                placeholder="Informe ISAK · junio 2026"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Tipo</Label>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              >
                {TIPOS.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">URL del archivo</Label>
            <Input
              placeholder="https://…/informe.pdf"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Pegá el link del archivo (Drive compartido, Cloudinary, etc.). La subida directa
              llega con el deploy.
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setMostrarForm(false)}>Cancelar</Button>
            <Button onClick={guardar} disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar adjunto"}
            </Button>
          </div>
        </Seccion>
      )}

      {cargando ? (
        <p className="text-sm text-muted-foreground">Cargando adjuntos…</p>
      ) : adjuntos.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Todavía no hay documentos. Los dos PDF del informe ISAK van acá.
        </p>
      ) : (
        <div className="space-y-2">
          {adjuntos.map((a) => (
            <div
              key={a.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border bg-card p-3.5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <FileText className="h-[18px] w-[18px] text-muted-foreground" />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{a.nombre_archivo}</p>
                  <p className="text-xs text-muted-foreground">
                    {etiquetaTipo(a.tipo)} · {fechaHoraLegible(a.fecha)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(a.ruta, "_blank", "noopener,noreferrer")}
                >
                  <ExternalLink className="mr-1 h-3.5 w-3.5" /> Abrir
                </Button>
                <BotonBorrar onConfirm={() => borrar(a.id)} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
