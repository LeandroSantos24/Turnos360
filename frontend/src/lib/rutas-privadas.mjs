/**
 * Rutas que NO se indexan: el panel, el admin, impresión y las pantallas que
 * llegan con un token en la URL. La usan robots.ts y next.config.mjs
 * (X-Robots-Tag). Si se agrega una carpeta al panel, va acá también.
 */
export const RUTAS_PRIVADAS = [
  "admin", "login", "olvide-password", "restablecer", "verificar", "imprimir",
  "agenda", "caja", "campanas", "clientes", "cuenta", "cupones", "equipo",
  "estadisticas", "gift-cards", "inicio", "membresias", "metodos-pago",
  "mi-dia", "mi-pagina", "recursos", "reglas-reserva", "seguimiento",
  "servicios", "sucursales", "suscripcion", "whatsapp",
];
