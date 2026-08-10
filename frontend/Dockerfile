# Imagen de DESARROLLO del frontend Next.js.
# La de producción es Dockerfile.prod (multi-stage, output standalone).

FROM node:20-alpine

WORKDIR /app

# npm ci, no npm install.
#   npm install resuelve versiones nuevas al construir la imagen; npm ci
#   respeta package-lock.json al pie de la letra. Con install, el contenedor
#   y la máquina del desarrollador terminaban con árboles de dependencias
#   DISTINTOS corriendo el mismo código: el mismo build daba tamaños
#   distintos según dónde se corriera. Eso convierte cualquier bug raro en
#   una cacería de horas.
#   Dockerfile.prod ya usaba npm ci; ahora los dos hacen lo mismo.
COPY package.json package-lock.json ./
RUN npm ci

# El código se monta como volumen en docker-compose (no se copia acá), así
# los cambios se ven al instante.

# Correr como el usuario `node` (uid 1000), que la imagen ya trae.
#   Como root, todo lo que Next escribía en .next quedaba en el disco del
#   host con dueño root — y después `npm run build` desde afuera moría con
#   EACCES sobre .next/trace. Con uid 1000 los archivos quedan del usuario
#   normal de Linux y las dos formas de buildear conviven.
#   node_modules va con --chown para que npm pueda escribir su caché.
RUN mkdir -p /app/.next && chown -R node:node /app
USER node

EXPOSE 3000

CMD ["npm", "run", "dev"]
