# Dev image for the Smart Transit AI frontend (Next.js 16).
# Production hardening (multi-stage build, `next build` + `next start`, non-root)
# lands with the rest of the infra in P7. This image just runs the dev server.
FROM node:22-alpine

WORKDIR /app

# Install deps first so the layer caches across source-only changes.
COPY package.json package-lock.json ./
RUN npm install

# App source. node_modules is excluded via .dockerignore so the host's copy
# never shadows the image's install.
COPY . .

EXPOSE 3000

# Bind to 0.0.0.0 so the dev server is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
