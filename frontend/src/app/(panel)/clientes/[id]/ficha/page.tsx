"use client";

/**
 * Ficha clínica del paciente (/clientes/[id]/ficha) — pack nutrición.
 *
 * Cuatro pestañas:
 * - Anamnesis:  la entrevista de primera consulta (con notas libres).
 * - Evolución:  los controles de seguimiento, consulta a consulta.
 * - Mediciones: antropometría por fecha + gráficos de evolución.
 * - Adjuntos:   PDFs del ISAK, estudios y planes (por URL).
 *
 * Cada tab carga y guarda lo suyo; esta página solo trae al paciente
 * y maneja la navegación entre pestañas.
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";

import { obtenerCliente, Cliente } from "@/lib/clientes-api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TabAnamnesis } from "./tab-anamnesis";
import { TabEvolucion } from "./tab-evolucion";
import { TabMediciones } from "./tab-mediciones";
import { TabAdjuntos } from "./tab-adjuntos";

const TABS = [
  ["anamnesis", "Anamnesis"],
  ["evolucion", "Evolución"],
  ["mediciones", "Mediciones"],
  ["adjuntos", "Adjuntos"],
] as const;

type TabId = (typeof TABS)[number][0];

export default function FichaPage() {
  const params = useParams();
  const router = useRouter();
  const clienteId = Number(params.id);

  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [tab, setTab] = useState<TabId>("anamnesis");

  useEffect(() => {
    obtenerCliente(clienteId)
      .then(setCliente)
      .catch((e) =>
        toast.error(e instanceof ApiError ? e.message : "No se pudo cargar el paciente"),
      );
  }, [clienteId]);

  const nombre = cliente ? `${cliente.nombre} ${cliente.apellido ?? ""}`.trim() : "…";

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      {/* Encabezado */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="font-[family-name:var(--font-syne)] text-2xl font-bold">
            Ficha clínica
          </h1>
          <p className="text-sm text-muted-foreground">{nombre}</p>
        </div>
      </div>

      {/* Pestañas (pill, estilo del panel) */}
      <div className="flex flex-wrap gap-2">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === id
                ? "border-primary bg-primary/10 text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Contenido del tab activo */}
      {tab === "anamnesis" && <TabAnamnesis clienteId={clienteId} />}
      {tab === "evolucion" && <TabEvolucion clienteId={clienteId} />}
      {tab === "mediciones" && <TabMediciones clienteId={clienteId} />}
      {tab === "adjuntos" && <TabAdjuntos clienteId={clienteId} />}
    </div>
  );
}
