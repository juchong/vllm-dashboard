# Frontend Dockerfile

FROM node:18-alpine as builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install && npm cache clean --force

# Build the application
COPY . .
RUN npm run test && npm run build

# Production image
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

ENV BACKEND_UPSTREAM=vllm-dashboard-backend
ENV BACKEND_PORT=8000

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
