/**
 * Celulares argentinos → el formato de wa.me (`549` + 10 dígitos).
 *
 * Espejo de `backend/app/core/telefono.py::normalizar_ar`, con la misma regla
 * de fondo: si no se puede saber con certeza qué número es, devuelve null en
 * vez de adivinar. Un recordatorio mandado al número equivocado le llega a un
 * desconocido con el nombre y el horario del cliente.
 *
 * El 15 y el 9 son la misma cosa dicha de dos maneras (cómo se marca un
 * celular desde adentro y desde afuera del país): WhatsApp quiere el 9 y sin
 * el 15. Con los dos, o con ninguno, el mensaje no llega.
 *
 * Verificado con `npm run check:telefono` contra los mismos casos que el
 * backend.
 */

const LARGO_NACIONAL = 10;

export function telefonoWa(texto: string | null | undefined): string | null {
  let d = (texto ?? "").replace(/\D/g, "");
  if (!d) return null;

  // Prefijo internacional escrito como 00: 0054 11 ...
  if (d.startsWith("00")) d = d.slice(2);

  let nacional = d;
  if (d.startsWith("54")) {
    let resto = d.slice(2);
    // 54 9 ...: el 9 de celular se saca acá y se vuelve a poner al final.
    if ((resto.length === 11 || resto.length === 13) && resto.startsWith("9")) {
      resto = resto.slice(1);
    }
    nacional = resto;
  }

  // El 0 de larga distancia: 0261 ...
  if (nacional.startsWith("0")) nacional = nacional.slice(1);

  // El 15 va justo después del código de área (2 dígitos solo en el 11).
  if (nacional.length === LARGO_NACIONAL + 2) {
    const largos = nacional.startsWith("11") ? [2] : [3, 4];
    for (const largo of largos) {
      if (nacional.slice(largo, largo + 2) === "15") {
        nacional = nacional.slice(0, largo) + nacional.slice(largo + 2);
        break;
      }
    }
  }

  if (nacional.length !== LARGO_NACIONAL) return null;
  if (nacional[0] === "0") return null;
  // 0000000000, 1111111111: relleno para pasar un campo obligatorio.
  if (new Set(nacional).size === 1) return null;

  return `549${nacional}`;
}

/** Link de WhatsApp con el mensaje ya escrito, o null si el número no sirve. */
export function linkWaCliente(
  telefono: string | null | undefined,
  mensaje: string,
): string | null {
  const numero = telefonoWa(telefono);
  return numero ? `https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}` : null;
}
