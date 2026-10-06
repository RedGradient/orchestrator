#!/bin/sh

# Подготавливает TLS для локального сайта, используемого интеграционными тестами Site Check.
#
# При каждом запуске контейнера создаются временный test CA и сертификат сервера
# для 127.0.0.1 и localhost. Fixture `site_check_server` копирует ca.crt в
# временный каталог pytest и передаёт его через SSL_CERT_FILE, поэтому проверка
# TLS использует настоящую цепочку доверия без хранения ключей в репозитории.
# Все файлы сертификатов живут только в контейнере и удаляются вместе с ним.

set -eu

cert_dir=/etc/nginx/test-certs
mkdir -p "$cert_dir"

openssl req -x509 -new -nodes -newkey rsa:2048 \
    -keyout "$cert_dir/ca.key" \
    -out "$cert_dir/ca.crt" \
    -days 2 \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -subj "/CN=Orchestrator Site Check Test CA"

openssl req -new -nodes -newkey rsa:2048 \
    -keyout "$cert_dir/site.key" \
    -out "$cert_dir/site.csr" \
    -subj "/CN=127.0.0.1"

cat > "$cert_dir/site.ext" <<'EOF'
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:127.0.0.1,DNS:localhost
EOF

openssl x509 -req \
    -in "$cert_dir/site.csr" \
    -CA "$cert_dir/ca.crt" \
    -CAkey "$cert_dir/ca.key" \
    -CAcreateserial \
    -out "$cert_dir/site.crt" \
    -days 2 \
    -sha256 \
    -extfile "$cert_dir/site.ext"

exec nginx -g 'daemon off;'
