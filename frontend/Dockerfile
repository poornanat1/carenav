# Build the Vite app, then serve the static bundle with Caddy.
# Two stages: node for the build, caddy for serving on $PORT.
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_API_BASE_URL is baked at build time; Railway passes it as a build arg/env.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
# Caddy config: serve /srv, SPA fallback to index.html, listen on $PORT.
COPY Caddyfile /etc/caddy/Caddyfile
