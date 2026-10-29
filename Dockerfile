# syntax=docker/dockerfile:1.7

FROM stagex/pallet-nodejs AS build-stage

COPY --from=stagex/user-hugo-extended:0.161.1 /usr/bin/hugo /usr/local/bin/hugo

ARG hugobuildargs
ENV HUGO_BUILD_ARGS=$hugobuildargs

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

RUN hugo ${HUGO_BUILD_ARGS}
RUN npx --no-install pagefind --site public --glob "**/items/*/index.html"

FROM stagex/user-caddy

COPY --from=stagex/core-musl / /
COPY --from=build-stage /app/public /srv

COPY <<'EOF' /etc/caddy/Caddyfile
{
	auto_https off
	admin off
}

:80 {
	root * /srv
	encode gzip zstd

	# Legacy URL redirects (301) from the pre-Hugo WordPress site. Caddy orders
	# `map` + `redir` ahead of `rewrite`/`file_server`, so matched paths redirect
	# before a 404. redirects.caddy lives in Hugo's static/, so it ships inside
	# public/ (the release artifact) and lands here at /srv/redirects.caddy.
	import /srv/redirects.caddy

	# Backward compatibility: /img/* serves from /assets/img/*
	rewrite /img/* /assets{uri}

	file_server
}
EOF

ENV XDG_CONFIG_HOME=/tmp/caddy-config \
    XDG_DATA_HOME=/tmp/caddy-data

EXPOSE 80
ENTRYPOINT ["/usr/bin/caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
