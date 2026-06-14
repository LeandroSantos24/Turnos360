# Imagen de desarrollo para el frontend Next.js
FROM node:20-alpine

WORKDIR /app

# Instalar dependencias primero (se cachea si package.json no cambia)
COPY package.json package-lock.json* ./
RUN npm install

# El código se monta como volumen en docker-compose, no se copia acá
# (así los cambios se ven al instante, igual que el backend)

EXPOSE 3000

CMD ["npm", "run", "dev"]