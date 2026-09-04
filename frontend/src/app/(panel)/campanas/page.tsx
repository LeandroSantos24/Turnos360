"use client";

/**
 * Campañas (/campanas).
 *
 * CÓMO ERA
 * ────────
 * Cinco tarjetas iguales, una debajo de la otra, todas del mismo gris y todas
 * con el mismo peso visual. Leídas de arriba abajo daban la impresión de ser
 * cinco variantes de lo mismo, cuando en realidad hacen tres trabajos que no
 * tienen nada que ver entre sí: evitar que el cliente falte, hacerlo volver, y
 * conseguir reputación. Y la configuración era mínima: los recordatorios salían
 * a 24 y 2 horas fijas, y el asunto del email lo escribíamos nosotros.
 *
 * CÓMO ES
 * ───────
 * Agrupadas por lo que hacen, cada grupo con su color, y con la explicación de
 * POR QUÉ conviene prender cada cosa arriba del grupo — que es lo que decide si
 * alguien la prende, no la descripción de qué hace.
 *
 * Lo que se puede configurar ahora y antes no:
 *  · las horas de cada recordatorio (el que atiende con turnos del mismo día
 *    necesita avisar 3 horas antes; a 24, la persona todavía no reservó);
 *  · el asunto del email, que es lo único que se ve en la bandeja;
 *  · cuánto esperar antes de pedir la reseña;
 *  · a cuántas visitas apuntar en «recuperar inactivos», para no escribirle a
 *    alguien que vino una sola vez.
 *
 * SE GUARDA SOLO
 * ──────────────
 * Antes había un botón «Guardar campañas» abajo de todo: se prendía un switch,
 * se scrolleaba, y si uno se iba de la pantalla sin llegar al botón, no se
 * guardaba nada y tampoco avisaba. Ahora cada cambio se guarda con un respiro
 * de 800 ms; el estado del guardado se ve arriba.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Cake,
  Check,
  Clock,
  HeartHandshake,
  Loader2,
  Megaphone,
  Send,
  Star,
} from "lucide-react";
import { toast } from "sonner";

import {
  obtenerAutomatizaciones,
  guardarAutomatizaciones,
  probarCampana,
  HORAS_RECORDATORIO,
  type Automatizaciones,
} from "@/lib/empresa-api";
import { ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

/** "3 horas antes" / "1 hora antes" / "2 días antes" — sin "48 horas antes". */
function textoAnticipacion(horas: number): string {
  if (horas >= 24 && horas % 24 === 0) {
    const d = horas / 24;
    return d === 1 ? "1 día antes" : `${d} días antes`;
  }
  return horas === 1 ? "1 hora antes" : `${horas} horas antes`;
}

function Grupo({
  titulo,
  porQue,
  tono,
  children,
}: {
  titulo: string;
  porQue: string;
  tono: string;
  children: React.ReactNode;
}) {
  return (
    <section className="aparece">
      <div className="mb-3">
        <h2
          className="text-xs font-bold uppercase tracking-[0.14em]"
          style={{ color: `hsl(${tono})` }}
        >
          {titulo}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{porQue}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Tarjeta({
  Icono,
  tono,
  titulo,
  descripcion,
  activa,
  onSwitch,
  tipo,
  children,
}: {
  Icono: typeof Bell;
  tono: string;
  titulo: string;
  descripcion: string;
  activa: boolean;
  onSwitch: (v: boolean) => void;
  tipo: string;
  children?: React.ReactNode;
}) {
  const [probando, setProbando] = useState(false);

  async function probar() {
    setProbando(true);
    try {
      // El destino ya no se pregunta: va al email del usuario que la pide, y
      // lo decide el backend. Cuando era un campo libre, con una cuenta de
      // prueba se podía mandar cualquier contenido a cualquier casilla desde
      // el remitente oficial de Turnos360.
      const r = await probarCampana(tipo);
      toast.success(r.detalle);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "No se pudo enviar la prueba");
    } finally {
      setProbando(false);
    }
  }

  return (
    <div
      className={`tarjeta overflow-hidden transition-shadow ${
        activa ? "shadow-[var(--sombra-tarjeta)]" : "shadow-none"
      }`}
      style={{ "--tono": tono } as React.CSSProperties}
    >
      <div className="flex items-start gap-4 p-5">
        <span className="cajita">
          <Icono className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{titulo}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">{descripcion}</p>
        </div>
        <Switch
          checked={activa}
          onCheckedChange={onSwitch}
          aria-label={`${activa ? "Apagar" : "Prender"} ${titulo}`}
        />
      </div>

      {activa && (
        <div className="space-y-4 border-t bg-muted/25 px-5 py-4">
          {children}
          <button
            type="button"
            onClick={probar}
            disabled={probando}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            {probando ? "Enviando…" : "Enviarme una prueba"}
          </button>
        </div>
      )}
    </div>
  );
}

/** Fila de píldoras para elegir un valor de una lista corta. */
function Opciones({
  etiqueta,
  ayuda,
  valor,
  opciones,
  onElegir,
  texto,
}: {
  etiqueta: string;
  ayuda?: string;
  valor: number;
  opciones: number[];
  onElegir: (v: number) => void;
  texto: (v: number) => string;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">{etiqueta}</Label>
      <div className="flex flex-wrap gap-1.5">
        {opciones.map((o) => (
          <button
            key={o}
            type="button"
            onClick={() => onElegir(o)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              o === valor
                ? "border-transparent bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {texto(o)}
          </button>
        ))}
      </div>
      {ayuda && <p className="text-xs text-muted-foreground">{ayuda}</p>}
    </div>
  );
}

/** El campo de asunto, igual en cumpleaños y en inactivos. */
function CampoAsunto({
  valor,
  onCambio,
  placeholder,
}: {
  valor: string;
  onCambio: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">
        Asunto del email{" "}
        <span className="font-normal">(vacío = el nuestro)</span>
      </Label>
      <Input value={valor} maxLength={120} placeholder={placeholder} onChange={(e) => onCambio(e.target.value)} />
      <p className="text-xs text-muted-foreground">
        Es lo único que ve tu cliente en la bandeja antes de decidir si abre.
      </p>
    </div>
  );
}

export default function CampanasPage() {
  const [cfg, setCfg] = useState<Automatizaciones | null>(null);
  const [estado, setEstado] = useState<"quieto" | "guardando" | "guardado">("quieto");
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const primeraCarga = useRef(true);

  useEffect(() => {
    obtenerAutomatizaciones()
      .then(setCfg)
      .catch(() => toast.error("No se pudieron cargar las campañas"));
  }, []);

  /**
   * Guardado automático con respiro.
   *
   * 800 ms: alcanza para que escribir un asunto entero sea UN pedido y no uno
   * por tecla, y es poco como para que nadie llegue a irse de la pantalla
   * antes de que salga.
   */
  const guardar = useCallback((datos: Automatizaciones) => {
    if (temporizador.current) clearTimeout(temporizador.current);
    setEstado("guardando");
    temporizador.current = setTimeout(async () => {
      try {
        await guardarAutomatizaciones(datos);
        setEstado("guardado");
        setTimeout(() => setEstado("quieto"), 2200);
      } catch (e) {
        setEstado("quieto");
        toast.error(e instanceof ApiError ? e.message : "No se pudo guardar");
      }
    }, 800);
  }, []);

  useEffect(() => {
    if (!cfg) return;
    // La primera vez que llega el estado del server no hay nada que guardar:
    // sin este freno, entrar a la pantalla dispararía un PUT solo.
    if (primeraCarga.current) {
      primeraCarga.current = false;
      return;
    }
    guardar(cfg);
  }, [cfg, guardar]);

  useEffect(() => () => {
    if (temporizador.current) clearTimeout(temporizador.current);
  }, []);

  function set<K extends keyof Automatizaciones>(clave: K, valor: Automatizaciones[K]) {
    setCfg((prev) => (prev ? { ...prev, [clave]: valor } : prev));
  }

  if (!cfg) {
    return (
      <div className="superficie min-h-full p-6 sm:p-8">
        <div className="mx-auto max-w-3xl space-y-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="tarjeta h-[88px] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const prendidas = [
    cfg.recordatorio_24h.activa,
    cfg.recordatorio_2h.activa,
    cfg.cumple.activa,
    cfg.resena_google.activa,
    cfg.inactivos.activa,
  ].filter(Boolean).length;

  return (
    <div className="superficie min-h-full p-6 sm:p-8">
      <div className="mx-auto max-w-3xl space-y-8">
        <div>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="titulo-pantalla">
                Tus <b>campañas</b>.
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Mensajes que salen solos. Prendés lo que quieras usar y el
                sistema se encarga — no hay que acordarse de nada.
              </p>
            </div>
            {/* El estado del guardado, arriba y siempre en el mismo lugar.
                Antes había un botón «Guardar» abajo de todo: quien prendía un
                switch y se iba de la pantalla perdía el cambio sin enterarse. */}
            <div className="flex h-6 shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
              {estado === "guardando" && (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Guardando…
                </>
              )}
              {estado === "guardado" && (
                <>
                  <Check className="h-3.5 w-3.5 text-primary" /> Guardado
                </>
              )}
              {estado === "quieto" && (
                <>
                  {prendidas} de 5 prendidas
                </>
              )}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-amber-300/60 bg-amber-50 p-3.5 text-xs leading-relaxed text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
            <b>Cumpleaños</b> y <b>recuperar inactivos</b> son promocionales:
            solo le llegan a quien aceptó recibir promociones (el tilde que
            aparece al reservar). Los recordatorios y el pedido de reseña son
            parte del servicio y le llegan a todos.
          </div>
        </div>

        {/* ── Anti-ausencias ───────────────────────────────────────── */}
        <Grupo
          titulo="Que no falten"
          tono="var(--acento-cielo)"
          porQue="El ausente es el dolor número uno del rubro: te quema una hora que ya no vendés. Dos avisos automáticos lo bajan más que cualquier otra cosa."
        >
          <Tarjeta
            Icono={Bell}
            tono="var(--acento-cielo)"
            titulo="Primer recordatorio"
            descripcion={`Le avisa al cliente ${textoAnticipacion(cfg.recordatorio_24h.horas_antes)}. El clásico: llega con tiempo para reprogramar en vez de faltar.`}
            activa={cfg.recordatorio_24h.activa}
            onSwitch={(v) => set("recordatorio_24h", { ...cfg.recordatorio_24h, activa: v })}
            tipo="recordatorio_24h"
          >
            <Opciones
              etiqueta="¿Cuánto antes?"
              valor={cfg.recordatorio_24h.horas_antes}
              opciones={HORAS_RECORDATORIO}
              texto={textoAnticipacion}
              onElegir={(h) => set("recordatorio_24h", { ...cfg.recordatorio_24h, horas_antes: h })}
              ayuda="Si trabajás con turnos del mismo día, 24 horas es demasiado: a esa altura la persona todavía no había reservado."
            />
          </Tarjeta>

          <Tarjeta
            Icono={Clock}
            tono="var(--acento-cielo)"
            titulo="Segundo recordatorio"
            descripcion={`El aviso corto, ${textoAnticipacion(cfg.recordatorio_2h.horas_antes)}. Juntos forman el doble recordatorio.`}
            activa={cfg.recordatorio_2h.activa}
            onSwitch={(v) => set("recordatorio_2h", { ...cfg.recordatorio_2h, activa: v })}
            tipo="recordatorio_2h"
          >
            <Opciones
              etiqueta="¿Cuánto antes?"
              valor={cfg.recordatorio_2h.horas_antes}
              opciones={HORAS_RECORDATORIO}
              texto={textoAnticipacion}
              onElegir={(h) => set("recordatorio_2h", { ...cfg.recordatorio_2h, horas_antes: h })}
              ayuda="Poné una anticipación distinta a la del primero: dos avisos a la misma hora se leen como un error tuyo."
            />
          </Tarjeta>
        </Grupo>

        {/* ── Fidelización ─────────────────────────────────────────── */}
        <Grupo
          titulo="Que vuelvan"
          tono="var(--acento-rosa)"
          porQue="Recuperar a un cliente que ya te conoce cuesta mucho menos que conseguir uno nuevo. Estas dos hablan con gente que ya te eligió alguna vez."
        >
          <Tarjeta
            Icono={Cake}
            tono="var(--acento-rosa)"
            titulo="Saludo de cumpleaños"
            descripcion="Lo saluda antes de su cumple, con el beneficio que definas. Una excusa para volver, con motivo."
            activa={cfg.cumple.activa}
            onSwitch={(v) => set("cumple", { ...cfg.cumple, activa: v })}
            tipo="cumple"
          >
            <Opciones
              etiqueta="¿Cuántos días antes?"
              valor={cfg.cumple.dias_antes}
              opciones={[0, 1, 3, 7, 15]}
              texto={(d) => (d === 0 ? "El día" : d === 1 ? "1 día" : `${d} días`)}
              onElegir={(d) => set("cumple", { ...cfg.cumple, dias_antes: d })}
              ayuda="Unos días antes funciona mejor que el mismo día: le das tiempo de sacar el turno."
            />
            <CampoAsunto
              valor={cfg.cumple.asunto}
              placeholder="🎂 Te tenemos una sorpresa"
              onCambio={(v) => set("cumple", { ...cfg.cumple, asunto: v })}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Beneficio (lo honrás vos en el local)
              </Label>
              <Textarea
                rows={2}
                maxLength={500}
                placeholder="20% en cualquier servicio durante tu semana de cumple 🎉"
                value={cfg.cumple.mensaje}
                onChange={(e) => set("cumple", { ...cfg.cumple, mensaje: e.target.value })}
              />
            </div>
          </Tarjeta>

          <Tarjeta
            Icono={HeartHandshake}
            tono="var(--acento-rosa)"
            titulo="Recuperar clientes inactivos"
            descripcion={`Al que lleva ${cfg.inactivos.dias} días o más sin venir le llega un «te extrañamos» con tu oferta. Se le avisa una sola vez.`}
            activa={cfg.inactivos.activa}
            onSwitch={(v) => set("inactivos", { ...cfg.inactivos, activa: v })}
            tipo="inactivos"
          >
            <Opciones
              etiqueta="¿Cuántos días sin venir?"
              valor={cfg.inactivos.dias}
              opciones={[30, 45, 60, 90, 120, 180]}
              texto={(d) => `${d} días`}
              onElegir={(d) => set("inactivos", { ...cfg.inactivos, dias: d })}
              ayuda="Poné un poco más que tu frecuencia normal. Si tus clientes vienen cada mes, 45 días ya es señal de que algo pasó."
            />
            <Opciones
              etiqueta="¿A quién le escribimos?"
              valor={cfg.inactivos.min_visitas}
              opciones={[1, 2, 3, 5]}
              texto={(v) => (v === 1 ? "A todos" : `Con ${v}+ visitas`)}
              onElegir={(v) => set("inactivos", { ...cfg.inactivos, min_visitas: v })}
              ayuda="«Te extrañamos» a alguien que vino una sola vez no es fidelizar: es escribirle a un desconocido. Con 2 o más hablás solo con quien ya había vuelto."
            />
            <CampoAsunto
              valor={cfg.inactivos.asunto}
              placeholder="Hace rato que no te vemos"
              onCambio={(v) => set("inactivos", { ...cfg.inactivos, asunto: v })}
            />
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Oferta para que vuelva (opcional)
              </Label>
              <Textarea
                rows={2}
                maxLength={500}
                placeholder="Volvé este mes y tenés 15% en cualquier servicio"
                value={cfg.inactivos.mensaje}
                onChange={(e) => set("inactivos", { ...cfg.inactivos, mensaje: e.target.value })}
              />
            </div>
          </Tarjeta>
        </Grupo>

        {/* ── Reputación ───────────────────────────────────────────── */}
        <Grupo
          titulo="Que te encuentren"
          tono="var(--acento-ambar)"
          porQue="Las reseñas de Google son lo que decide si alguien que no te conoce entra o sigue de largo. Pedirlas a mano no escala; así salen solas."
        >
          <Tarjeta
            Icono={Star}
            tono="var(--acento-ambar)"
            titulo="Reseña en Google"
            descripcion="Después de cada turno le pide al cliente una reseña. Reputación en piloto automático."
            activa={cfg.resena_google.activa}
            onSwitch={(v) => set("resena_google", { ...cfg.resena_google, activa: v })}
            tipo="resena_google"
          >
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Link para reseñar tu negocio en Google
              </Label>
              <Input
                placeholder="https://g.page/r/…/review"
                value={cfg.resena_google.link}
                maxLength={300}
                onChange={(e) =>
                  set("resena_google", { ...cfg.resena_google, link: e.target.value })
                }
              />
              <p className="text-xs text-muted-foreground">
                Lo sacás de tu Perfil de Empresa en Google → «Pedir reseñas».
              </p>
            </div>
            <Opciones
              etiqueta="¿Cuánto después del turno?"
              valor={cfg.resena_google.horas_despues}
              opciones={[0, 2, 4, 24, 48]}
              texto={(h) =>
                h === 0 ? "Al toque" : h >= 24 ? `${h / 24} día${h > 24 ? "s" : ""}` : `${h} h`
              }
              onElegir={(h) =>
                set("resena_google", { ...cfg.resena_google, horas_despues: h })
              }
              ayuda="Al toque es el peor momento: la persona está pagando y saliendo. Unas horas después ya está en su casa y el buen rato es un recuerdo."
            />
            {!cfg.resena_google.link.trim() && (
              <p className="rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-200">
                Sin el link, la campaña queda prendida pero no puede mandar
                nada.
              </p>
            )}
          </Tarjeta>
        </Grupo>

        <div className="flex items-center gap-2 pt-2 text-xs text-muted-foreground">
          <Megaphone className="h-3.5 w-3.5 shrink-0" />
          <p>
            Todo sale por email y el cliente necesita tener el suyo cargado.
            Probá cada una con «Enviarme una prueba» antes de dejarla andando.
          </p>
        </div>
      </div>
    </div>
  );
}
