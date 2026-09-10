FROM node:20-slim AS build
WORKDIR /app
# Copy the lockfile too and use `npm ci`, so an image build installs the exact
# dependency tree the repository pins rather than re-resolving it.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]