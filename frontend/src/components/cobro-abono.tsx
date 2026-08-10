"use client";

/**
 * Bloque de cobro al asignar una membresía.
 *
 * Existe porque asignar un abono NO cobraba nada: el cliente pagaba $50.000,
 * el negocio los tenía en el bolsillo y el sistema no se enteraba. No entraba
 * a la caja, no salía en el arqueo ni en la facturación. Y como después los
 * turnos de ese cliente salen en $0, el abono quedaba como costo visible e
 * ingreso invisible: la pantalla de rentabilidad mostraba pérdida donde había
 * ganancia.
 *
 * Vive en components/ y no adentro de un diálogo porque hay DOS pantallas que
 * asignan membresías (desde la ficha del cliente y desde Membresías), y si el
 * cobro estuviera en una sola, la otra seguiría dejando plata sin registrar.
 *
 * "Sin cobrar" es una opción legítima y explícita: una membresía de cortesía
 * (canje, compensación por un problema) no tiene que inventar un ingreso.
 */

import { useEffect, useState } from "react";

import { listarMetodos, type MetodoPago } from "@/lib/finanzas-api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface DatosCobroAbono {
  metodo_pago_id: number | null;
  monto_cobrado: number | null;
}

/** Valor centinela del selector: "no cobrar nada". */
const CORTESIA = "cortesia";

export function CobroAbono({
  activo,
  precioPlan,
  valor,
  onChange,
}: {
  /** Se recargan los métodos cada vez que el diálogo se abre. */
  activo: boolean;
  /** Precio del plan elegido: se sugiere como monto. */
  precioPlan: number | null;
  valor: DatosCobroAbono;
  onChange: (v: DatosCobroAbono) => void;
}) {
  const [metodos, setMetodos] = useState<MetodoPago[]>([]);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!activo) return;
    setCargando(true);
    listarMetodos()
      .then((m) => setMetodos(m.filter((x) => x.activo)))
      .catch(() => setMetodos([]))
      .finally(() => setCargando(false));
  }, [activo]);

  // Al cambiar de plan, se sugiere su precio mientras el usuario no haya
  // escrito un monto propio. Sin esto, elegir el plan después del monto
  // dejaba un importe que no correspondía a nada.
  useEffect(() => {
    if (valor.metodo_pago_id === null) return;
    if (valor.monto_cobrado === null && precioPlan !== null) {
      onChange({ ...valor, monto_cobrado: precioPlan });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [precioPlan]);

  const seleccion =
    valor.metodo_pago_id === null ? CORTESIA : String(valor.metodo_pago_id);

  const metodoElegido = metodos.find((m) => m.id === valor.metodo_pago_id);
  const monto = valor.monto_cobrado ?? precioPlan ?? 0;
  const comision = metodoElegido
    ? Math.round((monto * metodoElegido.comision_pct) / 100)
    : 0;

  return (
    <div className="space-y-3 rounded-xl border bg-muted/30 p-3">
      <div className="space-y-2">
        <Label htmlFor="cobro-metodo">Cobro del abono</Label>
        {/* <select> nativo a propósito: este bloque aparece adentro de un
            diálogo y el Select de la librería abre su panel en un portal,
            que en algunos navegadores queda tapado por el overlay. Acá lo
            que importa es que se pueda cobrar, no la estética. */}
        <select
          id="cobro-metodo"
          className="h-10 w-full rounded-md border bg-background px-3 text-sm"
          value={seleccion}
          onChange={(e) => {
            const v = e.target.value;
            onChange({
              metodo_pago_id: v === CORTESIA ? null : Number(v),
              monto_cobrado: v === CORTESIA ? null : (valor.monto_cobrado ?? precioPlan),
            });
          }}
        >
          <option value={CORTESIA}>Sin cobrar (cortesía)</option>
          {metodos.map((m) => (
            <option key={m.id} value={String(m.id)}>
              {m.nombre}
              {m.comision_pct > 0 ? ` · ${m.comision_pct}% comisión` : ""}
            </option>
          ))}
        </select>
        {!cargando && metodos.length === 0 && (
          <p className="text-xs text-amber-600">
            No hay métodos de pago cargados. Creá uno en Finanzas → Métodos
            para poder registrar el cobro.
          </p>
        )}
      </div>

      {valor.metodo_pago_id !== null && (
        <div className="space-y-2">
          <Label htmlFor="cobro-monto">Monto cobrado</Label>
          <Input
            id="cobro-monto"
            type="number"
            min={0}
            value={valor.monto_cobrado ?? ""}
            placeholder={precioPlan !== null ? String(precioPlan) : "0"}
            onChange={(e) =>
              onChange({
                ...valor,
                monto_cobrado: e.target.value === "" ? null : Number(e.target.value),
              })
            }
          />
          <p className="text-xs text-muted-foreground">
            {comision > 0
              ? `Entra a la caja de hoy. Comisión estimada $${comision.toLocaleString("es-AR")}.`
              : "Entra a la caja de hoy y suma a la facturación del período."}
          </p>
        </div>
      )}

      {valor.metodo_pago_id === null && (
        <p className="text-xs text-muted-foreground">
          No se registra ningún ingreso. La membresía queda marcada como
          cortesía y no cuenta en la rentabilidad del plan.
        </p>
      )}
    </div>
  );
}
