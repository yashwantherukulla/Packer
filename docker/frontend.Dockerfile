# syntax=docker/dockerfile:1
FROM node:20-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS serve
COPY --from=build /app/dist /usr/share/nginx/html
# SPA fallback + /api and /ws proxy to the api service are provided by compose-mounted nginx conf
EXPOSE 80
