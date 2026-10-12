"use client";

/** Configuración del super-admin (/admin/configuracion): por ahora, la marca. */

import { Encabezado } from "../_ui";
import { PestanasAuditoria } from "../auditoria/pestanas";
import { MarcaTurnos360 } from "../marca-turnos360";

export default function ConfiguracionAdmin() {
  return (
    <div>
      <Encabezado titulo="Auditoría y configuración" />
      <PestanasAuditoria />
      <MarcaTurnos360 />
    </div>
  );
}
