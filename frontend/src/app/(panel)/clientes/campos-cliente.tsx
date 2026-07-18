"use client";

/**
 * Campos del formulario de cliente, compartidos entre crear y editar.
 *
 * Recibe el estado (un objeto con todos los campos) y un setter que actualiza
 * un campo puntual. Así crear y editar usan exactamente los mismos campos sin
 * duplicar el formulario. Agrupados en: Datos personales / Contacto / CRM.
 */

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/** La forma de los datos del cliente en el formulario. */
export interface DatosCliente {
  nombre: string;
  apellido: string;
  dni: string;
  email: string;
  telefono: string;
  fecha_nacimiento: string;
  canal_adquisicion: string;
  acepta_marketing: boolean;
  etiquetas: string[];
  observaciones: string;
}

/** Valores iniciales vacíos (para el form de crear). */
export const CLIENTE_VACIO: DatosCliente = {
  nombre: "",
  apellido: "",
  dni: "",
  email: "",
  telefono: "",
  fecha_nacimiento: "",
  canal_adquisicion: "",
  acepta_marketing: false,
  etiquetas: [],
  observaciones: "",
};

// Opciones del desplegable de canal (de dónde llegó el cliente).
const CANALES = [
  { valor: "web", label: "Reserva online" },
  { valor: "instagram", label: "Instagram" },
  { valor: "tiktok", label: "TikTok" },
  { valor: "referido", label: "Referido" },
  { valor: "google", label: "Google" },
  { valor: "paso_por_la_puerta", label: "Pasó por la puerta" },
  { valor: "otro", label: "Otro" },
];

// Etiquetas predefinidas (chips). Se pueden activar/desactivar.
const ETIQUETAS_DISPONIBLES = ["VIP", "Frecuente", "Nuevo", "Moroso"];

interface CamposClienteProps {
  datos: DatosCliente;
  onCambio: <K extends keyof DatosCliente>(campo: K, valor: DatosCliente[K]) => void;
}

export function CamposCliente({ datos, onCambio }: CamposClienteProps) {
  /** Activa o desactiva una etiqueta. */
  function toggleEtiqueta(etiqueta: string) {
    const tiene = datos.etiquetas.includes(etiqueta);
    if (tiene) {
      onCambio(
        "etiquetas",
        datos.etiquetas.filter((e) => e !== etiqueta),
      );
    } else {
      onCambio("etiquetas", [...datos.etiquetas, etiqueta]);
    }
  }

  return (
    <div className="space-y-5">
      {/* Datos personales */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Datos personales
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="c-nombre">Nombre *</Label>
            <Input
              id="c-nombre"
              value={datos.nombre}
              onChange={(e) => onCambio("nombre", e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-apellido">Apellido</Label>
            <Input
              id="c-apellido"
              value={datos.apellido}
              onChange={(e) => onCambio("apellido", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-dni">DNI</Label>
            <Input
              id="c-dni"
              value={datos.dni}
              onChange={(e) => onCambio("dni", e.target.value)}
              placeholder="40123456"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-nacimiento">Fecha de nacimiento</Label>
            <Input
              id="c-nacimiento"
              type="date"
              value={datos.fecha_nacimiento}
              onChange={(e) => onCambio("fecha_nacimiento", e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Contacto */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Contacto
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="c-telefono">Teléfono</Label>
            <Input
              id="c-telefono"
              value={datos.telefono}
              onChange={(e) => onCambio("telefono", e.target.value)}
              placeholder="+54 9 261…"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="c-email">Email</Label>
            <Input
              id="c-email"
              type="email"
              value={datos.email}
              onChange={(e) => onCambio("email", e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>¿Cómo llegó?</Label>
          <Select
            value={datos.canal_adquisicion || undefined}
            onValueChange={(v) => onCambio("canal_adquisicion", v ?? "")}
          >
            <SelectTrigger>
              <SelectValue placeholder="Elegí un canal" />
            </SelectTrigger>
            <SelectContent>
              {CANALES.map((c) => (
                <SelectItem key={c.valor} value={c.valor}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* CRM */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Notas y etiquetas
        </p>
        <div className="space-y-2">
          <Label>Etiquetas</Label>
          <div className="flex flex-wrap gap-2">
            {ETIQUETAS_DISPONIBLES.map((etiqueta) => {
              const activa = datos.etiquetas.includes(etiqueta);
              return (
                <button
                  key={etiqueta}
                  type="button"
                  onClick={() => toggleEtiqueta(etiqueta)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    activa
                      ? "border-primary bg-primary/15 text-primary"
                      : "border-border text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {etiqueta}
                </button>
              );
            })}
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="c-obs">Observaciones</Label>
          <Textarea
            id="c-obs"
            value={datos.observaciones}
            onChange={(e) => onCambio("observaciones", e.target.value)}
            placeholder="Le gusta el degradé, viene cada 15 días…"
            rows={3}
          />
        </div>
      </div>
      {/* Consentimiento de marketing (Ley 25.326). Los recordatorios del turno
          NO dependen de esto: son parte del servicio que el cliente pidió. */}
      <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border p-3">
        <input
          type="checkbox"
          checked={datos.acepta_marketing}
          onChange={(e) => onCambio("acepta_marketing", e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
        />
        <span className="text-xs leading-relaxed text-muted-foreground">
          <b className="text-foreground">Acepta recibir promociones por email</b>
          <br />
          Necesario para mandarle campañas de cumpleaños o de recuperación. Los
          recordatorios del turno le llegan igual.
        </span>
      </label>

    </div>
  );
}