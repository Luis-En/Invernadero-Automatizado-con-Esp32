# Fail2ban para el invernadero (opcional, defensa en profundidad)

La aplicación ya bloquea intentos por IP y por usuario, y Nginx limita
`/api/auth/login` a 10 peticiones/minuto por IP. Fail2ban añade un baneo a nivel
de red durante 1 hora (con incremento) cuando ve 5 respuestas 401/403/429.

## Requisitos

- Docker publica los puertos a través de `FORWARD`, así que el baneo debe ir a
  la cadena `DOCKER-USER` (incluido en `action.d/greenhouse-docker.conf`).
- El frontend monta `./data/logs/nginx` en `/var/log/nginx`; el log de acceso
  queda en el host y Fail2ban puede leerlo.
- Todo el tráfico de la UI debe entrar por Nginx (puerto 5173). La API está
  publicada solo en `127.0.0.1:8000`, así que no se puede saltar el límite de
  Nginx desde la LAN.

## Instalación (host Debian/Ubuntu/Raspberry Pi OS)

```bash
sudo apt update && sudo apt install -y fail2ban

sudo cp deploy/fail2ban/filter.d/greenhouse-login.conf /etc/fail2ban/filter.d/
sudo cp deploy/fail2ban/action.d/greenhouse-docker.conf /etc/fail2ban/action.d/
sudo cp deploy/fail2ban/jail.d/greenhouse.local /etc/fail2ban/jail.d/

# Sustituye el marcador por la ruta real del proyecto
sudo sed -i "s|__PROJECT_DIR__|$PWD|" /etc/fail2ban/jail.d/greenhouse.local

sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban
```

## Verificación

```bash
sudo fail2ban-client status
sudo fail2ban-client status greenhouse-login
sudo iptables -S DOCKER-USER

# Simular 6 fallos (desde otra máquina o forzando el límite)
for i in $(seq 1 6); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://TU_HOST:5173/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"nadie","password":"mal"}'
done
```

## Rotación de logs

```bash
sudo cp deploy/logrotate/greenhouse /etc/logrotate.d/greenhouse
sudo sed -i "s|__PROJECT_DIR__|$PWD|" /etc/logrotate.d/greenhouse
sudo logrotate -d /etc/logrotate.d/greenhouse
```

Después de los 5 primeros fallos deberías ver la IP en
`fail2ban-client status greenhouse-login` y una regla DROP en `DOCKER-USER`.

## Desbloquear una IP

```bash
sudo fail2ban-client set greenhouse-login unbanip 192.168.1.50
sudo iptables -D DOCKER-USER -s 192.168.1.50 -j DROP
```

## Alternativa sin Fail2ban

Si no quieres instalar Fail2ban:

- Mantén el límite de Nginx y el bloqueo persistente de la aplicación.
- Añade reglas de firewall para permitir 5173 solo desde tu red/VPN:
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 5173 proto tcp
  sudo ufw deny 5173/tcp
  ```
- No publiques nunca el puerto 8000 en `0.0.0.0`; ya está en loopback.

## Notas

- `ignoreip` incluye solo loopback. Si te bloqueas a ti mismo por pruebas,
  añade tu IP a `ignoreip` o usa `unbanip`.
- Si usas Tailscale/Cloudflare Tunnel, el `$remote_addr` de Nginx puede ser el
  proxy, no el teléfono. En ese caso configura `real_ip` en Nginx o aplica el
  baneo en el proxy perimetral.
