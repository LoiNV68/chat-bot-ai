# --- Stage 1: Build the React Application ---
FROM node:18-alpine AS builder

WORKDIR /app

# Khai báo các biến môi trường để Vite build tĩnh vào mã JS
ARG VITE_API_BASE_URL
ARG VITE_API_PREFIX
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_PREFIX=$VITE_API_PREFIX

COPY package.json package-lock.json ./
# npm ci giúp cài đặt nhanh và chuẩn xác so với npm install
RUN npm ci

COPY . .
RUN npm run build

# --- Stage 2: Serve with NGINX ---
FROM nginx:alpine

# Xóa cấu hình mặc định của NGINX
RUN rm /etc/nginx/conf.d/default.conf

# Copy file cấu hình NGINX hỗ trợ React Router SPA
COPY nginx.conf /etc/nginx/conf.d/

# Copy thư mục build tĩnh từ Stage 1
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
