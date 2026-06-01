# ============================================================
# Stage 1: Build static assets
# No build-time URL args — all config is injected at runtime
# via docker-entrypoint.sh from env vars / ConfigMap.
# ============================================================
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
# Use npm install instead of npm ci: the lock file is generated on Windows so
# optional platform-specific packages (@emnapi/*) for Linux Alpine are absent,
# causing npm ci to fail. npm install resolves the correct platform packages.
RUN npm install

COPY . .
RUN npm run build

# ============================================================
# Stage 2: Serve with nginx (non-root, port 8080)
# ============================================================
FROM nginx:1.25-alpine

# Copy built assets, nginx config, and entrypoint
COPY --from=build /app/dist      /usr/share/nginx/html
COPY nginx.conf                  /etc/nginx/nginx.conf
COPY docker-entrypoint.sh        /docker-entrypoint.sh

# Make entrypoint executable and give nginx user ownership of the html
# directory so docker-entrypoint.sh can write config.js.
# (In k8s with readOnlyRootFilesystem an emptyDir is used instead — see k8s/.)
RUN chmod +x /docker-entrypoint.sh \
 && chown -R nginx:nginx /usr/share/nginx/html

# Run as nginx user (uid 101) — never root
USER nginx

EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
