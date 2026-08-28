"use client";

/**
 * Confirmación de acciones críticas, para todo el sistema.
 *
 * Por qué un hook y no un <AlertDialog> en cada pantalla: las acciones que hay
 * que proteger no son todas botones. Hay switches (pausar una empresa),
 * íconos de tacho adentro de un chip (borrar una franja horaria) y acciones
 * que salen de un menú. Cablear el diálogo declarativo en cada una obliga a
 * un estado `aConfirmar` por pantalla, y es exactamente el trabajo que se
 * saltea el que agrega el botón número 40.
 *
 * Con esto, proteger una acción es una línea:
 *
 *     const confirmar = useConfirmar();
 *     ...
 *     if (!(await confirmar({
 *       titulo: "¿Regalar 30 días?",
 *       descripcion: "Le vas a mover el vencimiento a la empresa X.",
 *       textoAccion: "Sí, renovar",
 *       destructivo: true,
 *     }))) return;
 *
 * Devuelve una promesa que resuelve true si el usuario aceptó y false si
 * canceló o cerró el diálogo. Nunca levanta.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

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

export type OpcionesConfirmar = {
  titulo: string;
  /** Qué va a pasar, en concreto. Nombrá el objeto y el número. */
  descripcion?: string;
  textoAccion?: string;
  textoCancelar?: string;
  /** Pinta el botón en rojo. Para lo que borra o no se puede deshacer. */
  destructivo?: boolean;
};

type Pedido = OpcionesConfirmar & { resolver: (ok: boolean) => void };

const Ctx = createContext<((o: OpcionesConfirmar) => Promise<boolean>) | null>(
  null,
);

export function ConfirmarProvider({ children }: { children: React.ReactNode }) {
  const [pedido, setPedido] = useState<Pedido | null>(null);
  // El resolver vive en un ref además del estado: si el diálogo se cierra por
  // Escape o por click afuera, hay que resolver la promesa igual. Sin esto,
  // el `await` del llamador queda colgado para siempre y la pantalla parece
  // trabada.
  const pendiente = useRef<((ok: boolean) => void) | null>(null);

  const confirmar = useCallback((o: OpcionesConfirmar) => {
    return new Promise<boolean>((resolver) => {
      pendiente.current = resolver;
      setPedido({ ...o, resolver });
    });
  }, []);

  function cerrar(ok: boolean) {
    pendiente.current?.(ok);
    pendiente.current = null;
    setPedido(null);
  }

  const valor = useMemo(() => confirmar, [confirmar]);

  return (
    <Ctx.Provider value={valor}>
      {children}
      <AlertDialog
        open={pedido !== null}
        onOpenChange={(abierto) => {
          if (!abierto) cerrar(false);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pedido?.titulo}</AlertDialogTitle>
            {pedido?.descripcion && (
              <AlertDialogDescription>
                {pedido.descripcion}
              </AlertDialogDescription>
            )}
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => cerrar(false)}>
              {pedido?.textoCancelar ?? "Cancelar"}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => cerrar(true)}
              className={
                pedido?.destructivo
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : undefined
              }
            >
              {pedido?.textoAccion ?? "Confirmar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Ctx.Provider>
  );
}

export function useConfirmar() {
  const ctx = useContext(Ctx);
  if (!ctx) {
    throw new Error(
      "useConfirmar() necesita un <ConfirmarProvider> arriba en el árbol " +
        "(está montado en el layout del panel y en el del admin).",
    );
  }
  return ctx;
}
