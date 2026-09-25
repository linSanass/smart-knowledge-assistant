# =========================
# 构建阶段
# =========================

FROM node:22-alpine AS build

WORKDIR /app

# 先只拷依赖清单，依赖没变时这层能命中缓存
COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run build


# =========================
# 运行阶段
# =========================

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# 容器内仍是 nginx 默认的 80，
# 由 compose 映射到宿主机的 5173 —— backend 的 CORS 白名单就是 5173
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
