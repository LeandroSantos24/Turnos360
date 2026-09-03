"use client";

/**
 * Métodos de cobro (/metodos-pago).
 *
 * CÓMO ERA
 * ────────
 * Una lista de renglones grises, y para un negocio recién dado de alta, ni
 * eso: la tabla nacía vacía y la pantalla decía «Todavía no cargaste métodos.
 * Empezá con Efectivo, Débito, Transferencia…». Le pedíamos a alguien que
 * acaba de entrar que escriba de memoria los mismos cinco nombres que escribe
 * todo el mundo y que además adivine la comisión de cada uno — y hasta que no
 * lo hacía no podía registrar un solo cobro.
 *
 * CÓMO ES
 * ───────
 * Los cinco de siempre ya están (los siembra el alta, ver
 * services/metodos_pago.py). Acá se prenden, se apagan y se les corrige la
 * comisión. Cada uno es una tarjeta con su ícono, su color, lo que le
 * descuenta y —para los que el cliente elige al reservar— las instrucciones
 * que va a leer.
 *
 * LAS COMISIONES QUE VIENEN CARGADAS SON UN PUNTO DE PARTIDA
 * ─────────────────────────────────────────────────────────
 * Están las publicadas de Mercado Pago sin IVA, que es como las piensa el
 * comerciante. Cada negocio tiene la suya —la de su posnet, la negociada con
 * su banco— y cambian seguido. La pantalla lo dice en vez de dejar creer que
 * son la verdad, porque de ese número sale el neto de cada cobro.
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { toast } from "sonner";
import {
  Banknote,
  CreditCard,
  Landmark,
  Plus,
  QrCode,
  Wallet,
  Pencil,
  Trash2,
  Info,
} from "lucide-react";

import {
  listarMetodos,
  crearMetodo,
  editarMetodo,
  borrarMetodo,
  MetodoPago,
  ClaveMetodo,
} from "@/lib/finanzas-api";
import { ApiError } from "@/lib/api";
import { RequiereDueno } from "@/components/requiere-rol";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/**
 * La identidad visual de cada medio de fábrica.
 *
 * `pieDeAyuda` es lo que hace que la pantalla enseñe en vez de solo listar:
 * dice de dónde sale la comisión y qué implica cada medio. Un dueño que no
 * sabe que el crédito le come el 4 % lo descubre acá y no a fin de mes.
 */
const PINTA: Record<
  ClaveMetodo,
  { Icono: typeof Wallet; tono: string; pieDeAyuda: string; pideInstrucciones: boolean }
> = {
  efectivo: {
    Icono: Banknote,
    tono: "var(--acento-lima)",
    pieDeAyuda: "Sin comisión. Entra directo a la caja del local.",
    pideInstrucciones: true,
  },
  debito: {
    Icono: CreditCard,
    tono: "var(--acento-cielo)",
    pieDeAyuda: "Lo que te descuenta tu posnet o tu billetera por cada débito.",
    pideInstrucciones: false,
  },
  credito: {
    Icono: CreditCard,
    tono: "var(--acento-violeta)",
    pieDeAyuda: "El más caro de los cinco. Ojo con las cuotas: suman aparte.",
    pideInstrucciones: false,
  },
  transferencia: {
    Icono: Landmark,
    tono: "var(--acento-ambar)",
    pieDeAyuda: "Sin comisión. Cargá tu alias y tu CBU para que el cliente los vea.",
    pideInstrucciones: true,
  },
  mp_qr: {
    Icono: QrCode,
    tono: "var(--acento-teal)",
    pieDeAyuda: "Acreditación inmediata. Es el medio por donde entran las señas.",
    pideInstrucciones: true,
  },
};

const PINTA_PROPIO = {
  Icono: Wallet,
  tono: "var(--acento-rosa)",
  pieDeAyuda: "Método propio de tu negocio.",
  pideInstrucciones: true,
};

function pintaDe(m: MetodoPago) {
  return m.clave ? PINTA[m.clave] : PINTA_PROPIO;
}

/** "4.20" → "4,2 %" — sin decimales de adorno y con la coma de acá. */
function comisionTexto(pct: number): string {
  if (!pct) return "Sin comisión";
  const n = Number(pct);
  const txt = Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0$/, "");
  return `${txt.replace(".", ",")} % de comisión`;
}

function TarjetaMetodo({
  metodo,
  indice,
  onToggle,
  onEditar,
  onBorrar,
}: {
  metodo: MetodoPago;
  indice: number;
  onToggle: () => void;
  onEditar: () => void;
  onBorrar: () => void;
}) {
  const { Icono, tono, pieDeAyuda } = pintaDe(metodo);

  return (
    <div
      className={`tarjeta tarjeta-viva aparece p-5 ${
        metodo.activo ? "" : "opacity-60"
      }`}
      style={{ "--demora": `${indice * 45}ms` } as React.CSSProperties}
    >
      <div className="flex items-start gap-4">
        <span className="cajita" style={{ "--tono": tono } as React.CSSProperties}>
          <Icono className="h-5 w-5" />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className="font-semibold">{metodo.nombre}</p>
            {metodo.clave === null && (
              <span className="pildora" style={{ "--tono": tono } as React.CSSProperties}>
                Propio
              </span>
            )}
          </div>
          <p className="mt-0.5 text-sm tabular-nums text-muted-foreground">
            {comisionTexto(metodo.comision_pct)}
          </p>
          <p className="mt-1.5 text-xs text-muted-foreground">{pieDeAyuda}</p>

          {metodo.instrucciones && (
            <p className="mt-3 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Tu cliente lee: </span>
              {metodo.instrucciones}
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <Switch
            checked={metodo.activo}
            onCheckedChange={onToggle}
            aria-label={`${metodo.activo ? "Apagar" : "Prender"} ${metodo.nombre}`}
          />
          <div className="flex">
            <Button variant="ghost" size="icon" onClick={onEditar} aria-label="Editar">
              <Pencil className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={onBorrar} aria-label="Quitar">
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ContenidoMetodosPago() {
  const [metodos, setMetodos] = useState<MetodoPago[]>([]);
  const [cargando, setCargando] = useState(true);
  const [dialogAbierto, setDialogAbierto] = useState(false);
  const [editando, setEditando] = useState<MetodoPago | null>(null);
  const [nombre, setNombre] = useState("");
  const [comision, setComision] = useState("");
  const [instrucciones, setInstrucciones] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [aQuitar, setAQuitar] = useState<MetodoPago | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setMetodos(await listarMetodos());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const activos = useMemo(() => metodos.filter((m) => m.activo).length, [metodos]);

  function abrirNuevo() {
    setEditando(null);
    setNombre("");
    setComision("");
    setInstrucciones("");
    setDialogAbierto(true);
  }

  function abrirEditar(m: MetodoPago) {
    setEditando(m);
    setNombre(m.nombre);
    setComision(String(m.comision_pct));
    setInstrucciones(m.instrucciones ?? "");
    setDialogAbierto(true);
  }

  async function guardar() {
    if (!nombre.trim()) return;
    setGuardando(true);
    try {
      const datos = {
        nombre: nombre.trim(),
        comision_pct: Number(comision) || 0,
        instrucciones: instrucciones.trim() || null,
      };
      if (editando) {
        await editarMetodo(editando.id, datos);
        toast.success("Listo, lo actualizamos");
      } else {
        await crearMetodo(datos);
        toast.success("Método agregado");
      }
      setDialogAbierto(false);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function toggleActivo(m: MetodoPago) {
    // Optimista: el switch se mueve al toque y se revierte si el server dice
    // que no. Esperar el ida y vuelta para mover un switch se siente roto.
    const previo = metodos;
    setMetodos((prev) =>
      prev.map((x) => (x.id === m.id ? { ...x, activo: !x.activo } : x)),
    );
    try {
      await editarMetodo(m.id, { activo: !m.activo });
    } catch (err) {
      setMetodos(previo);
      toast.error(err instanceof ApiError ? err.message : "No se pudo actualizar");
    }
  }

  async function confirmarQuitar() {
    if (!aQuitar) return;
    try {
      await borrarMetodo(aQuitar.id);
      toast.success(`${aQuitar.nombre} ya no aparece al cobrar`);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo quitar");
    } finally {
      setAQuitar(null);
    }
  }

  // Un método de fábrica, o uno con historia, se apaga en vez de borrarse. La
  // pantalla lo dice ANTES de que la persona confirme, no después: un cartel
  // que explica lo que ya pasó llega tarde.
  const seApaga = aQuitar !== null && aQuitar.clave !== null;

  return (
    <div className="superficie min-h-full p-6 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="titulo-pantalla">
              Tus <b>cobros</b>.
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Cómo cobra tu negocio. Prendé los que uses; la comisión se
              descuenta del neto en cada cobro.
            </p>
          </div>
          <Button onClick={abrirNuevo} className="shrink-0">
            <Plus className="mr-1.5 h-4 w-4" /> Agregar otro
          </Button>
        </div>

        {!cargando && metodos.length > 0 && (
          <p className="mb-4 text-xs text-muted-foreground">
            {activos} de {metodos.length} prendidos
          </p>
        )}

        {cargando ? (
          <div className="space-y-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="tarjeta h-[104px] animate-pulse" />
            ))}
          </div>
        ) : metodos.length === 0 ? (
          /* No debería verse nunca: el alta siembra los cinco. Queda por si
             alguna empresa vieja quedó sin ninguno — y ahí lo importante es
             que el botón esté a la vista, no el texto. */
          <div className="tarjeta vacio">
            <span className="vacio-icono">
              <Wallet className="h-8 w-8" />
            </span>
            <p className="font-semibold">Todavía no hay con qué cobrar</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Agregá el primero y ya vas a poder registrar cobros en la agenda y
              en la caja.
            </p>
            <Button onClick={abrirNuevo} className="mt-4">
              <Plus className="mr-1.5 h-4 w-4" /> Agregar un método
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {metodos.map((m, i) => (
              <TarjetaMetodo
                key={m.id}
                metodo={m}
                indice={i}
                onToggle={() => toggleActivo(m)}
                onEditar={() => abrirEditar(m)}
                onBorrar={() => setAQuitar(m)}
              />
            ))}
          </div>
        )}

        {!cargando && metodos.length > 0 && (
          <div className="mt-6 flex gap-3 rounded-xl border border-dashed p-4 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              Las comisiones que vienen cargadas son las publicadas de Mercado
              Pago sin IVA, como punto de partida. Corregilas con las tuyas
              —las de tu posnet, las que negociaste con tu banco—: de ese
              número sale el neto de cada cobro y el resultado de tu caja.
            </p>
          </div>
        )}
      </div>

      <Dialog open={dialogAbierto} onOpenChange={setDialogAbierto}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editando ? `Editar ${editando.nombre}` : "Nuevo método de cobro"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="m-nombre">Nombre *</Label>
              <Input
                id="m-nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Ualá, Cuenta DNI, Naranja X…"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="m-comision">Comisión (%)</Label>
              <Input
                id="m-comision"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={comision}
                onChange={(e) => setComision(e.target.value)}
                placeholder="0"
              />
              <p className="text-xs text-muted-foreground">
                Lo que te descuentan por cada cobro. Dejá 0 si no te descuentan
                nada.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="m-instrucciones">
                Instrucciones para el cliente{" "}
                <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Textarea
                id="m-instrucciones"
                value={instrucciones}
                onChange={(e) => setInstrucciones(e.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="Transferí al alias barberia.elfaro y mandanos el comprobante por WhatsApp."
              />
              <p className="text-xs text-muted-foreground">
                Es lo que lee tu cliente al elegir este medio en tu página de
                reservas.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogAbierto(false)}>
              Cancelar
            </Button>
            <Button onClick={guardar} disabled={guardando || !nombre.trim()}>
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={aQuitar !== null} onOpenChange={(o) => !o && setAQuitar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {seApaga
                ? `¿Apagar ${aQuitar?.nombre}?`
                : `¿Quitar ${aQuitar?.nombre}?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {seApaga ? (
                <>
                  Es uno de los medios de siempre, así que no se borra: deja de
                  aparecer al cobrar y lo podés volver a prender cuando quieras.
                  Los cobros ya hechos con él no se tocan.
                </>
              ) : (
                <>
                  Deja de aparecer al cobrar. Si ya registraste cobros con él, se
                  apaga en vez de borrarse, para que la caja de esos días siga
                  cuadrando.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmarQuitar}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {seApaga ? "Apagar" : "Quitar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function MetodosPagoPage() {
  return (
    <RequiereDueno>
      <ContenidoMetodosPago />
    </RequiereDueno>
  );
}
