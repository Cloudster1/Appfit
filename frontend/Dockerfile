FROM node:22-alpine AS dev
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

FROM dev AS build
RUN pnpm build

# Runs as a non-root user on port 8080 (Kubernetes restricted pod security).
FROM nginxinc/nginx-unprivileged:1.29-alpine AS prod
ENV APPFIT_BACKEND_URL=http://backend:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
