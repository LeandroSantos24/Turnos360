"use client";

/**
 * Horario de atención de un recurso, en su propia página.
 *
 * El lugar natural para tocar horarios ahora es /recursos (la lista arriba y
 * el horario del recurso elegido abajo, sin cambiar de pantalla). Esta página
 * se mantiene para los links directos y los marcadores que ya existían, y usa
 * exactamente el mismo componente.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { obtenerRecurso, Recurso } from "@/lib/recursos-api";
import { ApiError } from "@/lib/api";
import { RequiereDueno } from "@/components/requiere-rol";
import { Button } from "@/components/ui/button";
import { HorarioSemanal } from "../../horario-semanal";

function ContenidoHorarios() {
  const params = useParams();
  const router = useRouter();
  const recursoId = Number(params.id);

  const [recurso, setRecurso] = useState<Recurso | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setRecurso(await obtenerRecurso(recursoId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, [recursoId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (cargando) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">Cargando horarios…</p>
      </div>
    );
  }

  if (error || !recurso) {
    return (
      <div className="p-8">
        <Button variant="outline" size="sm" onClick={() => router.back()}>
          <ArrowLeft size={16} className="mr-1" /> Volver
        </Button>
        <p className="mt-4 text-sm text-destructive">
          {error ?? "Recurso no encontrado"}
        </p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-4">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => router.push("/recursos")}
        >
          <ArrowLeft size={16} className="mr-1" /> Volver a recursos
        </Button>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">Horario de {recurso.nombre}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Agregá una o varias franjas por día. Un día sin franjas queda cerrado.
        </p>
      </div>

      <HorarioSemanal recursoId={recurso.id} />
    </div>
  );
}

export default function HorariosRecursoPage() {
  return (
    <RequiereDueno>
      <ContenidoHorarios />
    </RequiereDueno>
  );
}
