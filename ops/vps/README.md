# VPS runbook — zoshyt-prod (крок 7 плану)

Первинне налаштування сервера руками, крок за кроком. Послідовність та
сама, що й для lozar-prod (2026-09-06); відмінності zoshyt позначені
**[≠ lozar]**. Після кожного блоку — перевірка; не йти далі, поки вона
не пройшла. Секретів у цьому файлі нема і бути не може.

Рішення, на які спирається: ADR-0005 (один VPS + compose, Caddy),
ADR-0014 (postgres лише на loopback), ADR-0013 (теги образів).

## 0. На Mac: ключі

Три ключі ed25519, у кожного своя роль. Приватні — лише на своїх
машинах і в менеджері паролів.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/zoshyt_admin  -C zoshyt-admin    # [С], з парольною фразою
ssh-keygen -t ed25519 -f ~/.ssh/zoshyt_deploy -C zoshyt-deploy   # для GitHub Actions, БЕЗ фрази
```

**[≠ lozar]** третій ключ — [К] генерує на своїй машині
(`-C zoshyt-admin-k`) і передає лише `.pub`: деплой ламатиметься не за
розкладом, доступ потрібен обом.

## 1. Hetzner: сервер і DNS

- Cloud Console → новий сервер: CX23 (x86, 4 ГБ; НЕ ARM/CAX — образ
  збирається під amd64), локація FI або DE, Ubuntu 24.04, ім'я
  `zoshyt-prod`. У «SSH keys» додати `zoshyt_admin.pub` — перший вхід
  під root буде по ключу, без пароля на пошту.
- **[≠ lozar]** Cloudflare DNS: запис `A app → <IPv4 сервера>`,
  СІРА хмарка (DNS only) — TLS робить Caddy, проксі Cloudflare
  зламав би видачу сертифіката.

Перевірка: `dig +short app.zoshyt.in.ua` повертає IP сервера.

## 2. Перший вхід (root): оновлення, юзер deploy

```bash
ssh -i ~/.ssh/zoshyt_admin root@<IP>
```

```bash
apt-get update && apt-get -y upgrade
timedatectl set-timezone UTC && timedatectl | grep "Time zone"
hostnamectl set-hostname zoshyt-prod
```

```bash
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy
```

Ключі для deploy — вставити ТРИ публічні ключі (admin, admin-k, deploy):

```bash
mkdir -p /home/deploy/.ssh
cat > /home/deploy/.ssh/authorized_keys <<'EOF'
<вміст zoshyt_admin.pub>
<вміст ключа [К].pub>
<вміст zoshyt_deploy.pub>
EOF
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

Чесно про ризик: ключ zoshyt_deploy лежить у секретах GitHub і заходить
тим самим юзером з sudo без пароля, тобто фактично це root. Розділення
юзерів майже нічого не дало б — група docker і так рівна root. Тому
захист тут — 2FA на GitHub і ruleset на main, не права на сервері.

**Сесію root НЕ закривати** до кінця кроку 4 — це страховка, якщо
вхід під deploy не запрацює.

## 3. На Mac: аліас і перевірка входу

```bash
cat >> ~/.ssh/config <<'EOF'

Host zoshyt-prod
  HostName <IP>
  User deploy
  IdentityFile ~/.ssh/zoshyt_admin
  IdentitiesOnly yes
EOF
ssh zoshyt-prod 'whoami && sudo -n true && echo sudo-ok'
```

Перевірка: `deploy` і `sudo-ok`. Далі все — через `ssh zoshyt-prod`.

## 4. sshd: лише ключі, без root

```bash
sudo tee /etc/ssh/sshd_config.d/00-zoshyt-hardening.conf > /dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sudo sshd -t
sudo sshd -T | grep -Ei 'permitrootlogin|passwordauthentication|kbdinteractive'
sudo systemctl reload ssh
```

Перевірка з НОВОГО термінала: `ssh zoshyt-prod whoami` працює;
`ssh -i ~/.ssh/zoshyt_admin root@<IP>` — `Permission denied`. Лише
тепер закрити стару сесію root.

## 5. ufw

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp     # [≠ lozar] Caddy: ACME-перевірка і редирект на https
sudo ufw allow 443/tcp    # [≠ lozar] Mini App
sudo ufw enable
sudo ufw status verbose
```

**[≠ lozar] Docker обходить ufw.** Порти, які публікує контейнер
(`ports:` у compose), відкриваються в iptables ПОВЗ правила ufw. У
lozar назовні нічого не публікується, тому там це не важило. Тут
справжній захист — правило «`ports:` лише у caddy, а postgres — лише
`127.0.0.1:`» (ADR-0005, ADR-0014), а не ufw. Правила 80/443 вище — для
порядку і на випадок сервісів поза Docker.

## 6. fail2ban

```bash
sudo apt install -y fail2ban
sudo tee /etc/fail2ban/jail.local > /dev/null <<'EOF'
[sshd]
enabled = true
EOF
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

## 7. unattended-upgrades

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades    # відповісти Yes
cat /etc/apt/apt.conf.d/20auto-upgrades            # обидва рядки "1"
```

## 8. Docker CE з офіційного репо

```bash
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
```

Перевірка — НОВОЮ сесією (група застосовується при вході), без sudo:

```bash
docker --version && docker compose version && systemctl is-enabled docker
docker run --rm hello-world
```

**[≠ lozar]** `docker login ghcr.io` НЕ потрібен: пакет
`ghcr.io/freedomserg/zoshyt` публічний (репо публічне, секретів в
образі нема).

## 9. /opt/zoshyt і .env

```bash
sudo mkdir -p /opt/zoshyt && sudo chown deploy:deploy /opt/zoshyt
umask 077 && touch /opt/zoshyt/.env && chmod 600 /opt/zoshyt/.env
```

**[≠ lozar]** `docker-compose.prod.yml`, `Caddyfile` і `ops/db/init.sh`
сюди кладе job deploy з того самого коміту, що й образ. Руками тут
живе лише `.env`:

```
APP_ENV=prod
AUTH_MODE=telegram
TELEGRAM_BOT_TOKEN=<токен @zoshyt_app_bot зі сховища>
WEBAPP_URL=https://app.zoshyt.in.ua
POSTGRES_PASSWORD=<згенерований>
ADMIN_CHAT_ID=<chat_id [С]>
HC_API_URL=
HC_BOT_URL=
HC_REMINDERS_URL=
```

- Пароль — `openssl rand -hex 24`: лише hex, бо він підставляється в
  URL підключення, і спецсимволи зламали б його. Одразу в менеджер
  паролів обох.
- `DB_URL` і `DB_MIGRATE_URL` сюди НЕ писати: їх збирає compose з
  `POSTGRES_PASSWORD`.
- `AUTH_MODE=dev` при `APP_ENV=prod` — процес впаде на старті. Так і
  задумано.

## 10. GitHub: секрети і перший деплой

Settings → Secrets and variables → Actions → Secrets:

| Секрет | Значення |
|---|---|
| `VPS_HOST` | IPv4 сервера |
| `VPS_SSH_KEY` | вміст `~/.ssh/zoshyt_deploy` (приватний, цілком, з рядками BEGIN/END) |
| `VPS_KNOWN_HOSTS` | вивід `ssh-keyscan <IP> 2>/dev/null` |

```bash
ssh-keyscan <IP> 2>/dev/null | pbcopy
```

ОСТАННЬОЮ — вкладка Variables: `DEPLOY_ENABLED` = `true`. Потім
Actions → Release → останній прогін → Re-run all jobs (або будь-який
merge у main).

Перший `up` на порожньому volume виконає `ops/db/init.sh` (ролі
zoshyt_migrate / zoshyt_app / zoshyt_readonly, ADR-0015), потім
`migrate` накотить ревізії, потім
стартують api і bot. Caddy сам отримає сертифікат — для цього DNS з
кроку 1 уже має вказувати на сервер.

## 11. ВИХІД кроку — перевірити все

```bash
ssh zoshyt-prod 'cd /opt/zoshyt && docker compose -f docker-compose.prod.yml ps'
ssh zoshyt-prod 'cd /opt/zoshyt && docker compose -f docker-compose.prod.yml logs migrate | tail -5'
curl -sS https://app.zoshyt.in.ua/health          # {"status":"ok"}, сертифікат валідний
curl -sSI http://app.zoshyt.in.ua | head -3       # 308 → https
```

- [ ] `ps`: postgres healthy, api / bot / caddy — Up, migrate — Exited (0).
- [ ] У логах migrate — `Running upgrade  -> 20260919_1`.
- [ ] `/health` по https відповідає; редирект з http є.
- [ ] Prod-бот відповідає на `/start`; кнопка меню відкриває Mini App
      з телефона.
- [ ] Ззовні відкриті лише 22, 80, 443: `nmap -Pn -p 22,80,443,5432,8000 <IP>`
      — 5432 і 8000 closed/filtered.
- [ ] `ssh zoshyt-prod 'sudo ss -tlnp | grep 5432'` — лише `127.0.0.1:5432`.
- [ ] Після цього прибрати умову `DEPLOY_ENABLED` з release.yml
      (як у lozar) окремим PR.

## 12. DBeaver до prod-бази (ADR-0014, ADR-0015)

Postgres слухає лише loopback сервера. У DBeaver: Main — host
`localhost`, port `5432`, database `zoshyt`, user `zoshyt_readonly`,
пароль — `POSTGRES_PASSWORD` з `.env`; вкладка SSH — host `<IP>`, user
`deploy`, ключ `~/.ssh/zoshyt_admin`. Роль `zoshyt_readonly` має лише
SELECT: «дивитися очима» фізично не може нічого записати.

Підводний камінь з lozar: macOS віддає застарілу зону `Europe/Kiev`, а
Postgres 17 відхиляє її на підключенні. У `dbeaver.ini` додати
`-Duser.timezone=UTC`.

## 13. Відкат

```bash
ssh zoshyt-prod
cd /opt/zoshyt
IMAGE_TAG=<sha12 або X.Y.Z> docker compose -f docker-compose.prod.yml up -d
```

Це відкочує образ; конфіги лишаються з останнього деплою. Відкат разом
з конфігами — Actions → Release → Re-run на старому коміті. Схему БД
відкат образу НЕ відкочує: ревізії alembic лише вперед.
