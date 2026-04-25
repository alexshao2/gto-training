# Multi-stage build: compile the Vite SPA, then serve it with nginx + reverse
# proxy /api and /api/ws/ to the backend service. Same-origin so no CORS.
ARG NODE_VERSION=20

FROM node:${NODE_VERSION}-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

# Empty VITE_API_BASE => the SPA uses same-origin relative paths like /api/...
# nginx (next stage) routes those to the backend container.
ENV VITE_API_BASE=""
RUN npm run build


FROM nginx:1.27-alpine AS runtime
RUN rm -rf /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/app.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
