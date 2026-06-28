# Multi-stage: npm build → nginx serve
FROM node:20-slim AS build
WORKDIR /app
COPY allahpan-web/package.json allahpan-web/package-lock.json ./
RUN npm ci --silent
COPY allahpan-web/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
