FROM node:20-alpine AS build

WORKDIR /app

RUN corepack enable && corepack prepare yarn@1.22.22 --activate

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ARG REACT_APP_BACKEND_URL=https://ecourt.demoapi.agrayianailabs.com
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL
# Runtime fallback for CSP when CSP_API_ORIGIN is unset (Easypanel env injection)
ENV CSP_API_ORIGIN=
ARG REACT_APP_SHOW_DEMO=false
ENV REACT_APP_SHOW_DEMO=$REACT_APP_SHOW_DEMO

RUN yarn build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
