# Frontend Dockerfile

FROM node:18-alpine as builder

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install && npm cache clean --force

# Build the application
COPY . .
RUN npm run build

# Production image
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
