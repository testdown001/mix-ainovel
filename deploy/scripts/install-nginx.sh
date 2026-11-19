#!/bin/sh
# Install a pinned, signature-verified upstream security release in Debian images.
set -eu
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
test "$ID" = debian
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
curl --fail --silent --show-error --retry 3 https://nginx.org/keys/nginx_signing.key -o /tmp/nginx_signing.key
gpg --batch --yes --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg /tmp/nginx_signing.key
gpg --batch --show-keys --with-colons /usr/share/keyrings/nginx-archive-keyring.gpg > /tmp/nginx-key-info
grep -q '^fpr:::::::::573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62:' /tmp/nginx-key-info
printf 'deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/mainline/debian %s nginx\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/nginx.list
printf 'Package: nginx\nPin: origin nginx.org\nPin-Priority: 900\n' > /etc/apt/preferences.d/99nginx
apt-get update
# Replace Debian nginx-common as well; main config is copied by the Dockerfile afterwards.
apt-get install -y --no-install-recommends -o Dpkg::Options::=--force-confold "nginx=1.31.9-1~${VERSION_CODENAME}" nginx-common-
nginx -v 2>&1 | grep -q 'nginx/1.31.9$'
rm -f /tmp/nginx_signing.key /tmp/nginx-key-info
rm -rf /var/lib/apt/lists/*
