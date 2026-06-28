"use client";

/**
 * Selector "Usuario vinculado" para el formulario de recurso.
 * Trae los usuarios de la empresa (endpoint /recursos/usuarios-disponibles) y
 * deshabilita los que ya están vinculados a OTRO recurso, respetando el 1-a-1.
 * El backend igual valida (409) por si acaso: esto es la ayuda visual.
 */

import { useEffect, useState } from "react";
import {
  listarUsuariosVinculables,
  UsuarioVinculable,
  Rol,
} from "@/lib/recursos-api";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const ROL_LABEL: Record<Rol, string> = {
  dueno: "Dueño",
  recepcion: "Recepción",
  profesional: "Profesional",
  admin: "Admin",
};

const SIN_VINCULAR = "none";

interface Props {
  value: number | null;
  onChange: (usuarioId: number | null) => void;
  /** Al editar: id del recurso actual, para no deshabilitar su propio usuario. */
  recursoActualId?: number | null;
}

export function SelectorUsuarioVinculado({
  value,
  onChange,
  recursoActualId = null,
}: Props) {
  const [usuarios, setUsuarios] = useState<UsuarioVinculable[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    setError(false);
    listarUsuariosVinculables()
      .then((data) => {
        if (vivo) setUsuarios(data);
      })
      .catch(() => {
        if (vivo) setError(true);
      })
      .finally(() => {
        if (vivo) setCargando(false);
      });
    return () => {
      vivo = false;
    };
  }, []);

  return (
    <div className="space-y-2">
      <Label>Usuario vinculado</Label>
      <Select
        value={value === null ? SIN_VINCULAR : String(value)}
        onValueChange={(v) => onChange(v === SIN_VINCULAR ? null : Number(v))}
        disabled={cargando || error}
      >
        <SelectTrigger>
          <SelectValue placeholder={cargando ? "Cargando…" : "Sin vincular"} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={SIN_VINCULAR}>Sin vincular</SelectItem>
          {usuarios.map((u) => {
            const ocupadoPorOtro =
              u.recurso_id !== null && u.recurso_id !== recursoActualId;
            return (
              <SelectItem
                key={u.id}
                value={String(u.id)}
                disabled={ocupadoPorOtro}
              >
                {u.nombre} · {ROL_LABEL[u.rol] ?? u.rol}
                {ocupadoPorOtro ? ` (ya en ${u.recurso_nombre})` : ""}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      {error ? (
        <p className="text-xs text-destructive">
          No se pudieron cargar los usuarios.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          Si lo atiende alguien con login (un barbero), vinculalo para que entre
          y vea solo su agenda.
        </p>
      )}
    </div>
  );
}
