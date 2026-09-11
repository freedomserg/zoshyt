# ADR-0005 — Хостинг: один VPS + Docker Compose, без k8s і managed free tier

Статус: accepted (2026-09)

## Контекст
Один design-partner, 1–5 викладачів на школу, аптайм некритичний.
Досвід [С] з k8s є, але це не аргумент його застосовувати.

## Рішення
Один Hetzner VPS (x86, 4 ГБ). docker-compose.prod.yml: caddy
(80/443, TLS Let's Encrypt автоматично, HSTS) → api; migrate
(one-shot) → api → bot → postgres. Сервер у UTC. Деплой — заміна
IMAGE_TAG + `compose pull && up -d`; відкат — той самий рядок зі
старим тегом.

## Альтернативи (відкинуті)
- k8s/k3s — оверкіл: нема що оркеструвати.
- Managed/free tier (Fly, Railway, …) — платформний ризик, ліміти,
  менше контролю за даними.
- Nginx + certbot — два інструменти замість одного Caddy.

## Наслідки
- Масштабування — вертикальне; повний down при падінні VPS —
  прийнятий ризик.
- Відкриті порти: лише 22, 80, 443.

## Для Claude Code
У prod-compose published ports має лише caddy. Усі сервіси —
restart: unless-stopped, logging json-file з max-size/max-file.
Жодної залежності від локального часу контейнера.
