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

import {
  EmpresaCobranza,
  PagoSuscripcion,
  ResumenCobranza,
  SemaforoColor,
  darProrroga,
  guardarFicha,
  historialPagos,
  listarCobranza,
  registrarPago,
  resumenCobranza,
} from "@/lib/admin-api";
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
};

const FILTROS: { valor: SemaforoColor | ""; label: string }[] = [
  { valor: "", label: "Todas" },
  { valor: "rojo", label: "Vencidas" },
  { valor: "amarillo", label: "Por vencer" },
  { valor: "verde", label: "Al día" },
  { valor: "gris", label: "Sin vencimiento" },
];

export default function CobranzaPage() {
  const [empresas, setEmpresas] = useState<EmpresaCobranza[]>([]);
  const [resumen, setResumen] = useState<ResumenCobranza | null>(null);
  const [color, setColor] = useState<SemaforoColor | "">("");
  const [buscar, setBuscar] = useState("");
  const [cargando, setCargando] = useState(true);
  const [cobrando, setCobrando] = useState<EmpresaCobranza | null>(null);
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
        <h1 className="text-2xl font-bold" style={{ fontFamily: "Syne, sans-serif" }}>
          Cobranza
        </h1>
        <p className="text-sm text-muted-foreground">
          A quién cobrarle, cuánto entró y qué está por vencer.
        </p>
      </div>

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
                const c = COLORES[e.semaforo_color];
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
                        <Button size="sm" onClick={() => setCobrando(e)}>
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
          onCerrar={() => setCobrando(null)}
          onListo={() => {
            setCobrando(null);
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
        style={{ fontFamily: "Syne, sans-serif" }}
      >
        {valor}
      </p>
      <p className="mt-0.5 truncate text-xs text-muted-foreground" title={pie}>
        {pie}
      </p>
    </div>
  );
}

function DialogCobro({
  empresa,
  onCerrar,
  onListo,
}: {
  empresa: EmpresaCobranza;
  onCerrar: () => void;
  onListo: () => void;
}) {
  const [monto, setMonto] = useState(String(empresa.precio_mensual ?? ""));
  const [metodo, setMetodo] = useState("transferencia");
  const [notas, setNotas] = useState("");
  const [renovar, setRenovar] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [historial, setHistorial] = useState<PagoSuscripcion[]>([]);

  useEffect(() => {
    historialPagos(empresa.id).then(setHistorial).catch(() => setHistorial([]));
  }, [empresa.id]);

  async function guardar() {
    const valor = Number(monto);
    if (!valor || valor <= 0) {
      toast.error("Ingresá un monto válido");
      return;
    }
    setGuardando(true);
    try {
      await registrarPago(empresa.id, { monto: valor, metodo, notas: notas || undefined, renovar });
      toast.success(
        renovar ? "Pago registrado · vencimiento +30 días" : "Pago registrado (sin renovar)",
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
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle style={{ fontFamily: "Syne, sans-serif" }}>
            Registrar pago · {empresa.nombre}
          </DialogTitle>
          <DialogDescription>
            {empresa.suscripcion_vence
              ? `Vence el ${empresa.suscripcion_vence} · ${empresa.semaforo_detalle}`
              : "Sin vencimiento definido"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1.5 text-sm">
              <span className="text-muted-foreground">Monto</span>
              <Input
                type="number"
                value={monto}
                onChange={(e) => setMonto(e.target.value)}
                placeholder="20000"
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

          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground">Notas (opcional)</span>
            <Input
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Ej: pagó por Mercado Pago el 18/7"
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
    precio_mensual: empresa.precio_mensual != null ? String(empresa.precio_mensual) : "",
    limite_recursos: empresa.limite_recursos != null ? String(empresa.limite_recursos) : "",
    notas_admin: empresa.notas_admin ?? "",
  });
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
      });
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
          <DialogTitle style={{ fontFamily: "Syne, sans-serif" }}>
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
            {campo("precio_mensual", "Cuota mensual", "20000", "number")}
            {campo("limite_recursos", "Tope de profesionales", "vacío = sin límite", "number")}
          </div>
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
