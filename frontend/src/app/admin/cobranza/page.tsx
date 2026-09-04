"use client";

/**
 * Cobranza del SaaS (/admin/cobranza).
 *
 * La pantalla para saber A QUIÉN COBRARLE de un vistazo, sin cruzar con el
 * Excel. Arriba, las tarjetas de balance; abajo, el listado con semáforo:
 *   verde    = al día
 *   amarillo = vence dentro de 7 días (hay que ir a cobrar)
 *   rojo     = venció (incluye los 10 días de prórroga)
 *   gris     = sin vencimiento (piloto bonificado)
 *
 * Acciones por empresa: registrar el pago (renueva 30 días), dar días de
 * gracia y editar la ficha comercial (precio pactado, CUIT, contacto).
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarPlus, DollarSign, Search, Users } from "lucide-react";
import { toast } from "sonner";
import { useConfirmar } from "@/components/confirmar";
import { AvisosDePago } from "./avisos-de-pago";

import {
  AvisoPago,
  EmpresaCobranza,
  PagoSuscripcion,
  ResumenCobranza,
  SemaforoColor,
  darProrroga,
  guardarFicha,
  setearSuscripcion,
  historialPagos,
  listarCobranza,
  registrarPago,
  resumenCobranza,
} from "@/lib/admin-api";
import { PLANES, PRECIO_MENSUAL } from "@/lib/precios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const PESOS = (n: number | null | undefined) =>
  n == null ? "—" : `$${Number(n).toLocaleString("es-AR")}`;

const COLORES: Record<SemaforoColor, { punto: string; chip: string; label: string }> = {
  verde: { punto: "bg-emerald-500", chip: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", label: "Al día" },
  amarillo: { punto: "bg-amber-500", chip: "bg-amber-500/10 text-amber-700 dark:text-amber-400", label: "Por vencer" },
  rojo: { punto: "bg-red-500", chip: "bg-red-500/10 text-red-700 dark:text-red-400", label: "Vencida" },
  gris: { punto: "bg-muted-foreground/40", chip: "bg-muted text-muted-foreground", label: "Sin vencimiento" },
  azul: { punto: "bg-sky-500", chip: "bg-sky-500/10 text-sky-700 dark:text-sky-400", label: "En prueba" },
};

const FILTROS: { valor: SemaforoColor | ""; label: string }[] = [
  { valor: "", label: "Todas" },
  { valor: "rojo", label: "Vencidas" },
  { valor: "amarillo", label: "Por vencer" },
  { valor: "verde", label: "Al día" },
  { valor: "azul", label: "En prueba" },
  { valor: "gris", label: "Sin vencimiento" },
];

export default function CobranzaPage() {
  const confirmar = useConfirmar();
  const [empresas, setEmpresas] = useState<EmpresaCobranza[]>([]);
  const [resumen, setResumen] = useState<ResumenCobranza | null>(null);
  const [color, setColor] = useState<SemaforoColor | "">("");
  const [buscar, setBuscar] = useState("");
  const [cargando, setCargando] = useState(true);
  const [cobrando, setCobrando] = useState<EmpresaCobranza | null>(null);
  // El aviso que abrió el diálogo, si vino de la bandeja. Es lo que permite
  // precargar el monto QUE DIJO QUE PAGÓ en vez del precio de lista.
  const [avisoActivo, setAvisoActivo] = useState<AvisoPago | null>(null);
  // Se incrementa al registrar un cobro para que la bandeja se vuelva a pedir.
  const [refrescoAvisos, setRefrescoAvisos] = useState(0);
  const [ficha, setFicha] = useState<EmpresaCobranza | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [lista, res] = await Promise.all([
        listarCobranza({ buscar: buscar || undefined, color: color || undefined }),
        resumenCobranza(),
      ]);
      setEmpresas(lista);
      setResumen(res);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo cargar la cobranza");
    } finally {
      setCargando(false);
    }
  }, [buscar, color]);

  useEffect(() => {
    const t = setTimeout(cargar, buscar ? 350 : 0); // debounce de la búsqueda
    return () => clearTimeout(t);
  }, [cargar, buscar]);

  async function prorroga(e: EmpresaCobranza, dias: number) {
    // Es ACUMULATIVA: el backend hace vence = base + dias. Tres clicks son
    // treinta días regalados, y no hay "quitar prórroga" en el panel.
    if (
      !(await confirmar({
        titulo: `¿Darle ${dias} días de gracia a ${e.nombre}?`,
        descripcion:
          "Se le mueve el vencimiento sin registrar ningún pago. Es acumulativa: " +
          "si la clickeás dos veces, son el doble de días. Desde el panel no se puede quitar.",
        textoAccion: `Sí, +${dias} días`,
      }))
    )
      return;
    try {
      await darProrroga(e.id, dias);
      toast.success(`${e.nombre}: +${dias} días de gracia`);
      cargar();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "No se pudo dar la prórroga");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--fuente-titulos)" }}>
          Cobranza
        </h1>
        <p className="text-sm text-muted-foreground">
          A quién cobrarle, cuánto entró y qué está por vencer.
        </p>
      </div>

      {/* Lo primero: quién dice que ya pagó y hay que confirmar en el banco. */}
      <AvisosDePago
        recargar={refrescoAvisos}
        onCobrar={(empresaId, aviso) => {
          const emp = empresas.find((e) => e.id === empresaId);
          if (emp) {
            setAvisoActivo(aviso);
            setCobrando(emp);
          } else {
            toast.error("Buscá el negocio en la lista para registrar el cobro");
          }
        }}
      />

      {/* Balance rápido */}
      {resumen && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tarjeta
            titulo="Cobrado este mes"
            valor={PESOS(resumen.cobrado_mes)}
            icono={<DollarSign className="h-4 w-4" />}
            tono="emerald"
            pie={
              resumen.por_metodo.length > 0
                ? resumen.por_metodo
                    .map((m) => `${m.metodo}: ${PESOS(m.total)}`)
                    .join(" · ")
                : "Sin pagos registrados"
            }
          />
          <Tarjeta
            titulo={`Por cobrar (${resumen.dias_aviso} días)`}
            valor={PESOS(resumen.pendiente_estimado)}
            icono={<CalendarPlus className="h-4 w-4" />}
            tono="amber"
            pie={
              `${resumen.empresas_por_vencer} empresa${resumen.empresas_por_vencer === 1 ? "" : "s"}` +
              (resumen.por_vencer_sin_precio > 0
                ? ` · ${resumen.por_vencer_sin_precio} sin precio cargado`
                : "")
            }
          />
          <Tarjeta
            titulo="Deuda vencida"
            valor={PESOS(resumen.deuda_vencida)}
            icono={<AlertTriangle className="h-4 w-4" />}
            tono="red"
            pie={`${resumen.empresas_vencidas} empresa${resumen.empresas_vencidas === 1 ? "" : "s"} pasada${resumen.empresas_vencidas === 1 ? "" : "s"} de fecha`}
          />
          <Tarjeta
            titulo="MRR"
            valor={PESOS(resumen.mrr)}
            icono={<Users className="h-4 w-4" />}
            tono="sky"
            pie="Suma de precios pactados activos"
          />
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-2">
        {FILTROS.map((f) => (
          <button
            key={f.valor || "todas"}
            onClick={() => setColor(f.valor)}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              color === f.valor
                ? "bg-primary text-primary-foreground"
                : "border hover:bg-muted/50"
            }`}
          >
            {f.label}
          </button>
        ))}
        <div className="relative ml-auto w-full sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Nombre, CUIT, email…"
            value={buscar}
            onChange={(e) => setBuscar(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Listado */}
      <div className="overflow-x-auto rounded-2xl border">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">Empresa</th>
              <th className="px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3 font-medium">Vence</th>
              <th className="px-4 py-3 text-right font-medium">Cuota</th>
              <th className="px-4 py-3 font-medium">Uso</th>
              <th className="px-4 py-3 text-right font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {cargando && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  Cargando…
                </td>
              </tr>
            )}
            {!cargando && empresas.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No hay empresas con ese filtro.
                </td>
              </tr>
            )}
            {!cargando &&
              empresas.map((e) => {
                // Fallback: un color nuevo del backend no puede tumbar la tabla.
                const c = COLORES[e.semaforo_color] ?? COLORES.gris;
                return (
                  <tr key={e.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${c.punto}`} />
                        <div className="min-w-0">
                          <button
                            onClick={() => setFicha(e)}
                            className="truncate font-medium hover:underline"
                          >
                            {e.nombre}
                          </button>
                          <p className="truncate text-xs text-muted-foreground">
                            {e.contacto_telefono || e.contacto_email || `/${e.slug}`}
                            {!e.activa && " · PAUSADA"}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${c.chip}`}>
                        {c.label}
                      </span>
                      {e.semaforo_en_prorroga && (
                        <span className="ml-1 text-xs text-muted-foreground">en gracia</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="tabular-nums">{e.suscripcion_vence ?? "—"}</span>
                      <p className="text-xs text-muted-foreground">{e.semaforo_detalle}</p>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {PESOS(e.precio_mensual)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          e.capacidad_excedida ? "font-medium text-amber-600" : undefined
                        }
                      >
                        {e.cantidad_recursos}
                        {e.limite_recursos != null ? `/${e.limite_recursos}` : ""} prof.
                      </span>
                      <p className="text-xs text-muted-foreground">
                        {e.cantidad_usuarios} usuario{e.cantidad_usuarios === 1 ? "" : "s"}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1.5">
                        <Button
                          size="sm"
                          onClick={() => {
                            setAvisoActivo(null);
                            setCobrando(e);
                          }}
                        >
                          Cobrar
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => prorroga(e, 10)}>
                          +10d
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>

      {cobrando && (
        <DialogCobro
          empresa={cobrando}
          aviso={avisoActivo}
          onCerrar={() => {
            setCobrando(null);
            setAvisoActivo(null);
          }}
          onListo={() => {
            setCobrando(null);
            setAvisoActivo(null);
            setRefrescoAvisos((n) => n + 1);
            cargar();
          }}
        />
      )}
      {ficha && (
        <DialogFicha
          empresa={ficha}
          onCerrar={() => setFicha(null)}
          onListo={() => {
            setFicha(null);
            cargar();
          }}
        />
      )}
    </div>
  );
}

function Tarjeta({
  titulo,
  valor,
  pie,
  icono,
  tono,
}: {
  titulo: string;
  valor: string;
  pie: string;
  icono: React.ReactNode;
  tono: "emerald" | "amber" | "red" | "sky";
}) {
  const fondos = {
    emerald: "bg-emerald-500/10 text-emerald-600",
    amber: "bg-amber-500/10 text-amber-600",
    red: "bg-red-500/10 text-red-600",
    sky: "bg-sky-500/10 text-sky-600",
  }[tono];
  return (
    <div className="rounded-2xl border p-4">
      <div className="flex items-center gap-2">
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${fondos}`}>
          {icono}
        </span>
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {titulo}
        </span>
      </div>
      <p
        className="mt-2 text-2xl font-bold tabular-nums"
        style={{ fontFamily: "var(--fuente-titulos)" }}
      >
        {valor}
      </p>
      <p className="mt-0.5 truncate text-xs text-muted-foreground" title={pie}>
        {pie}
      </p>
    </div>
  );
}

/**
 * Registrar un pago.
 *
 * ES LA PANTALLA DONDE SE PUEDE PERDER PLATA
 * ──────────────────────────────────────────
 * Los pagos por Mercado Pago los confirma el webhook y nadie los toca. Acá
 * llegan los otros: las transferencias, que las verifica una persona mirando
 * el banco. Un error acá no lo corrige ningún sistema — se descubre cuando el
 * cliente reclama que pagó Pro y lo dejaron en Inicial, o cuando el mes cierra
 * con un número que no da.
 *
 * Por eso el diálogo cambió de forma. Antes venía con el precio de LISTA
 * precargado y sin nada del aviso a la vista: había que acordarse de cuánto
 * había dicho el negocio y compararlo mentalmente. Ahora:
 *
 *   1. Si viene de un aviso, arriba está lo que la persona declaró: monto,
 *      comprobante, quién avisó y cuándo. No hay que ir a buscarlo.
 *   2. El monto viene precargado con lo AVISADO, no con el de lista. Se
 *      registra lo que pagó, no lo que debería haber pagado.
 *   3. Si avisado y esperado no coinciden, lo dice con todas las letras y
 *      ofrece un botón para usar el esperado. La diferencia se ve, no se
 *      calcula.
 *   4. Hay selector de plan: una transferencia hecha para pasar a Pro deja al
 *      negocio en Pro. Sin esto se cobraba el dinero sin entregar lo comprado.
 *   5. Abajo, antes de confirmar, dice en una línea qué va a pasar: el plan
 *      resultante y el vencimiento de antes → después.
 */
function DialogCobro({
  empresa,
  aviso,
  onCerrar,
  onListo,
}: {
  empresa: EmpresaCobranza;
  /** El aviso de transferencia que abrió esto, si vino de la bandeja. */
  aviso?: AvisoPago | null;
  onCerrar: () => void;
  onListo: () => void;
}) {
  // Lo que le corresponde cobrar: el precio pactado si lo tiene, si no el de
  // su plan, y de última el de lista. El pactado manda: para eso existe.
  const planActual = PLANES.find((p) => p.codigo === empresa.plan);
  const esperado =
    empresa.precio_mensual ?? (planActual?.precio || PRECIO_MENSUAL);

  // El monto arranca con lo AVISADO. Registrar lo que efectivamente entró es
  // lo correcto aunque no sea lo que debía entrar: si transfirió de menos, la
  // caja tiene que decir de menos, no el precio de lista.
  const [monto, setMonto] = useState(
    String(aviso?.monto ?? esperado),
  );
  const [metodo, setMetodo] = useState(aviso?.metodo || "transferencia");
  const [plan, setPlan] = useState(empresa.plan);
  const [notas, setNotas] = useState(
    aviso?.referencia ? `Comprobante ${aviso.referencia}` : "",
  );
  const [renovar, setRenovar] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [historial, setHistorial] = useState<PagoSuscripcion[]>([]);

  useEffect(() => {
    historialPagos(empresa.id).then(setHistorial).catch(() => setHistorial([]));
  }, [empresa.id]);

  const valor = Number(monto);
  const difiere = !!valor && Math.abs(valor - esperado) >= 1;
  const planElegido = PLANES.find((p) => p.codigo === plan);
  const cambiaPlan = plan !== empresa.plan;

  // El vencimiento que va a quedar: desde el actual si todavía no pasó, si no
  // desde hoy. Es la misma cuenta que hace el backend — acá solo se muestra
  // para que nadie confirme a ciegas.
  const venceDespues = (() => {
    if (!renovar) return empresa.suscripcion_vence;
    const hoy = new Date();
    const actual = empresa.suscripcion_vence
      ? new Date(`${empresa.suscripcion_vence}T00:00:00`)
      : null;
    const base = actual && actual > hoy ? actual : hoy;
    const d = new Date(base);
    d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  })();

  async function guardar() {
    if (!valor || valor <= 0) {
      toast.error("Ingresá un monto válido");
      return;
    }
    setGuardando(true);
    try {
      await registrarPago(empresa.id, {
        monto: valor,
        metodo,
        notas: notas || undefined,
        renovar,
        plan,
      });
      toast.success(
        cambiaPlan
          ? `Pago registrado · queda en ${planElegido?.etiqueta ?? plan}`
          : renovar
            ? "Pago registrado · vencimiento +30 días"
            : "Pago registrado (sin renovar)",
      );
      onListo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo registrar el pago");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "var(--fuente-titulos)" }}>
            Registrar pago · {empresa.nombre}
          </DialogTitle>
          <DialogDescription>
            {empresa.suscripcion_vence
              ? `Vence el ${empresa.suscripcion_vence} · ${empresa.semaforo_detalle}`
              : "Sin vencimiento definido"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* LO QUE DIJO EL CLIENTE. Está arriba de todo porque es lo que hay
              que ir a buscar al banco: el número de comprobante y el monto. */}
          {aviso && (
            <div className="rounded-xl border border-sky-500/40 bg-sky-500/5 p-3 text-sm">
              <p className="font-medium">Lo que avisó el negocio</p>
              <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">Dice que transfirió</span>
                  <p className="text-lg font-bold tabular-nums">{PESOS(aviso.monto)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Vos esperás</span>
                  <p className="text-lg font-bold tabular-nums">{PESOS(esperado)}</p>
                </div>
              </div>
              {aviso.referencia && (
                <p className="mt-2 break-all">
                  <span className="text-muted-foreground">Comprobante: </span>
                  <span className="font-mono">{aviso.referencia}</span>
                </p>
              )}
              <p className="mt-1 text-xs text-muted-foreground">
                {aviso.metodo}
                {aviso.avisado_por ? ` · lo cargó ${aviso.avisado_por}` : ""}
                {aviso.creado_en
                  ? ` · ${new Date(aviso.creado_en).toLocaleString("es-AR", {
                      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                    })}`
                  : ""}
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground">Monto que entró</span>
              <Input
                type="number"
                value={monto}
                onChange={(e) => setMonto(e.target.value)}
                placeholder={String(esperado)}
              />
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground">Método</span>
              <select
                value={metodo}
                onChange={(e) => setMetodo(e.target.value)}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              >
                <option value="transferencia">Transferencia</option>
                <option value="efectivo">Efectivo</option>
                <option value="mercadopago">Mercado Pago</option>
                <option value="otro">Otro</option>
              </select>
            </label>
          </div>

          {/* La diferencia se muestra calculada. Restar de cabeza mientras se
              mira el homebanking es exactamente donde se cometen los errores. */}
          {difiere && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/50 bg-amber-500/5 p-3 text-sm">
              <span>
                {valor > esperado ? "Pagó de más: " : "Falta: "}
                <span className="font-semibold tabular-nums">
                  {PESOS(Math.abs(valor - esperado))}
                </span>
                <span className="block text-xs text-muted-foreground">
                  Se registra lo que pusiste, no lo esperado.
                </span>
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setMonto(String(esperado))}
              >
                Usar {PESOS(esperado)}
              </Button>
            </div>
          )}

          {/* EL PLAN. Sin esto, cobrar una transferencia de upgrade dejaba al
              negocio en el plan viejo: plata cobrada, producto no entregado. */}
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Con este pago queda en</span>
            <select
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            >
              {PLANES.map((p) => (
                <option key={p.codigo} value={p.codigo}>
                  {p.etiqueta}
                  {p.precio > 0 ? ` · $${p.precio.toLocaleString("es-AR")}` : ""}
                  {p.codigo === empresa.plan ? " (actual)" : ""}
                </option>
              ))}
            </select>
            {cambiaPlan && (
              <span className="block text-xs text-amber-700 dark:text-amber-400">
                Cambia de {planActual?.etiqueta ?? empresa.plan} a{" "}
                {planElegido?.etiqueta ?? plan}
                {planElegido?.resumen ? ` — ${planElegido.resumen}` : ""}.
              </span>
            )}
          </label>

          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Notas (opcional)</span>
            <Input
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Ej: se ve en el banco el 18/7"
            />
          </label>

          <label className="flex items-start gap-2.5 rounded-xl bg-muted/40 p-3 text-sm">
            <input
              type="checkbox"
              checked={renovar}
              onChange={(e) => setRenovar(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              Renovar 30 días
              <span className="block text-xs text-muted-foreground">
                Si pagó dentro de los 10 días de gracia, se cuenta desde el vencimiento
                anterior. Si pagó más tarde, desde hoy. Destildá para anotar un pago
                parcial sin mover la fecha.
              </span>
            </span>
          </label>

          {/* Qué va a pasar al apretar el botón, en una línea. Confirmar sin
              saber el resultado es cómo se registran los pagos equivocados. */}
          <div className="rounded-xl border bg-muted/30 p-3 text-sm">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Al confirmar
            </p>
            <ul className="mt-1.5 space-y-1">
              <li>
                Entra <span className="font-semibold tabular-nums">{PESOS(valor || null)}</span>{" "}
                por {metodo} a la caja de {empresa.nombre}.
              </li>
              <li>
                Queda en plan{" "}
                <span className="font-semibold">{planElegido?.etiqueta ?? plan}</span>.
              </li>
              <li>
                Vence{" "}
                <span className="tabular-nums">
                  {empresa.suscripcion_vence ?? "—"}
                </span>{" "}
                → <span className="font-semibold tabular-nums">{venceDespues ?? "—"}</span>
                {!renovar && " (sin cambio)"}
              </li>
              {aviso && <li>El aviso sale de la bandeja.</li>}
            </ul>
          </div>

          {historial.length > 0 && (
            <div className="rounded-xl border">
              <p className="border-b px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Últimos pagos
              </p>
              <ul className="divide-y text-sm">
                {historial.slice(0, 5).map((p) => (
                  <li key={p.id} className="flex items-center justify-between px-3 py-2">
                    <span className="text-muted-foreground">
                      {p.fecha} · {p.metodo}
                    </span>
                    <span className="tabular-nums font-medium">{PESOS(p.monto)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando}>
              {guardando ? "Guardando…" : "Registrar pago"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DialogFicha({
  empresa,
  onCerrar,
  onListo,
}: {
  empresa: EmpresaCobranza;
  onCerrar: () => void;
  onListo: () => void;
}) {
  const [f, setF] = useState({
    razon_social: empresa.razon_social ?? "",
    cuit: empresa.cuit ?? "",
    contacto_nombre: empresa.contacto_nombre ?? "",
    contacto_email: empresa.contacto_email ?? "",
    contacto_telefono: empresa.contacto_telefono ?? "",
    precio_mensual:
      empresa.precio_mensual != null
        ? String(empresa.precio_mensual)
        : String(PRECIO_MENSUAL),
    limite_recursos: empresa.limite_recursos != null ? String(empresa.limite_recursos) : "",
    limite_sucursales:
      empresa.limite_sucursales != null ? String(empresa.limite_sucursales) : "",
    notas_admin: empresa.notas_admin ?? "",
  });
  // El plan va aparte porque no es parte de la ficha comercial: se guarda por
  // el endpoint de suscripción, que es el que valida contra la grilla.
  const [plan, setPlan] = useState<string>(empresa.plan ?? "gratuito");
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    setGuardando(true);
    try {
      await guardarFicha(empresa.id, {
        razon_social: f.razon_social || null,
        cuit: f.cuit || null,
        contacto_nombre: f.contacto_nombre || null,
        contacto_email: f.contacto_email || null,
        contacto_telefono: f.contacto_telefono || null,
        notas_admin: f.notas_admin || null,
        precio_mensual: f.precio_mensual ? Number(f.precio_mensual) : null,
        limite_recursos: f.limite_recursos ? Number(f.limite_recursos) : null,
        limite_sucursales: f.limite_sucursales ? Number(f.limite_sucursales) : null,
      });
      if (plan !== empresa.plan) {
        await setearSuscripcion(empresa.id, { plan });
      }
      toast.success("Ficha actualizada");
      onListo();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  const campo = (k: keyof typeof f, label: string, placeholder = "", tipo = "text") => (
    <label className="space-y-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Input
        type={tipo}
        value={f[k]}
        placeholder={placeholder}
        onChange={(e) => setF({ ...f, [k]: e.target.value })}
      />
    </label>
  );

  return (
    <Dialog open onOpenChange={(o) => !o && onCerrar()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "var(--fuente-titulos)" }}>
            Ficha comercial · {empresa.nombre}
          </DialogTitle>
          <DialogDescription>
            Datos internos de facturación. El negocio no los ve en su panel.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {campo("razon_social", "Razón social", "Estrella SRL")}
            {campo("cuit", "CUIT", "30-12345678-9")}
            {campo("contacto_nombre", "Contacto", "Lucas Estrella")}
            {campo("contacto_telefono", "Teléfono", "2615550001")}
            {campo("contacto_email", "Email", "lucas@negocio.com", "email")}
            {campo("precio_mensual", "Cuota mensual", String(PRECIO_MENSUAL), "number")}
            {campo("limite_recursos", "Tope de profesionales", "vacío = usa el plan", "number")}
            {campo("limite_sucursales", "Tope de locales", "vacío = usa el plan", "number")}
          </div>

          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Plan contratado</span>
            <select
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            >
              {PLANES.map((p) => (
                <option key={p.codigo} value={p.codigo}>
                  {p.etiqueta} — {p.resumen}
                </option>
              ))}
            </select>
            <span className="block text-xs text-muted-foreground">
              Define los topes de profesionales y locales. Los dos campos de
              arriba los pisan si los completás: sirven para hacerle un cupo
              especial a un cliente sin inventar un plan nuevo.
            </span>
          </label>
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Notas internas</span>
            <textarea
              value={f.notas_admin}
              onChange={(e) => setF({ ...f, notas_admin: e.target.value })}
              rows={3}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="Piloto bonificado hasta septiembre a cambio del testimonio."
            />
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <Button variant="outline" onClick={onCerrar}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
