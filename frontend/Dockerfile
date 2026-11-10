# Build the static bundle, then serve it from Nginx. The dev server is no
# longer the production entrypoint, so LAN clients get one origin (no CORS,
# no hardcoded localhost API URL).
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
