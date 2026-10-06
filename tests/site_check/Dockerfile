FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/
COPY entrypoint.sh /usr/local/bin/site-check-test-entrypoint

RUN chmod 0755 /usr/local/bin/site-check-test-entrypoint

ENTRYPOINT ["/usr/local/bin/site-check-test-entrypoint"]
