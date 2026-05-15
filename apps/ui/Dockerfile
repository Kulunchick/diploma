# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Копіюємо файли залежностей
COPY package*.json ./

# Встановлюємо залежності
RUN npm ci

# Копіюємо код застосунку
COPY . .

# Vite replaces import.meta.env.* at build time — pass vars as ARGs
ARG VITE_WS_BASE_URL=ws://localhost:8000
ARG VITE_USE_TEMPORAL_API=false
ENV VITE_WS_BASE_URL=$VITE_WS_BASE_URL
ENV VITE_USE_TEMPORAL_API=$VITE_USE_TEMPORAL_API

# Будуємо застосунок
RUN npm run build

# Production stage
FROM nginx:alpine

# Копіюємо збудований застосунок з попереднього етапу
COPY --from=build /app/dist /usr/share/nginx/html

# SPA routing: all unknown paths → index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]