# Intranet/Proxy-Setup (Beispiel)

Dieses Projekt ist so gedacht, dass es **nur im Intranet** läuft.
Das Firmennetz kann Internet haben, aber **die App darf nicht "nach draußen" sprechen**.

Der wichtigste Hebel dafür ist eine **Content-Security-Policy (CSP)** im Reverse Proxy
und eine **Firewall-Regel (Egress: Default Deny)** für die Server/Container.

## Zielbild

Browser -> Reverse Proxy (TLS + SSO + CSP) -> Backend API (FastAPI) -> DB

## CSP: verhindert Verbindungen ins Internet

Eine strenge CSP kann im Browser Verbindungen zu fremden Hosts blockieren.
Wichtig ist dabei `connect-src 'self'`.

Beispiel (vereinfachte CSP):

```http
Content-Security-Policy: default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'
```

Hinweis: In der Entwicklung (Vite) sind oft zusätzliche Direktiven nötig (z.B. wegen HMR).
Für die Produktion sollte man die CSP so streng wie möglich halten.

## Nginx Snippet (Beispiel)

```nginx
server {
  listen 443 ssl;
  server_name dashboard.intranet;

  # TLS-Zertifikat aus interner PKI
  ssl_certificate     /etc/nginx/certs/intranet.crt;
  ssl_certificate_key /etc/nginx/certs/intranet.key;

  # CSP + Security-Header
  add_header Content-Security-Policy "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'" always;
  add_header Referrer-Policy "no-referrer" always;
  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;

  # Frontend (statische Dateien)
  location / {
    root /var/www/dashboard-frontend;
    try_files $uri $uri/ /index.html;
  }

  # Backend API (nur intern erreichbar)
  location /api/ {
    proxy_pass http://backend:8000;

    # Identity/SSO-Hinweis:
    # Hier würden in der Praxis Identity-Headers oder ein JWT gesetzt,
    # z.B. aus Kerberos/NTLM/SAML/OIDC.
    # proxy_set_header X-User-Id ...;
    # proxy_set_header X-Station-Id ...;
    # proxy_set_header X-Roles ...;
  }
}
```

## Firewall/Egress

Zusätzlich zur CSP sollte der Host/Container **keinen Internet-Egress** haben:

- DNS nur intern
- HTTP/HTTPS nach extern blockieren
- ggf. erlaubte Ziele "allow-list" (z.B. interne Updateserver)
