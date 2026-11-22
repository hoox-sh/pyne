# Azure VM — Let's Encrypt cert via Cloudflare DNS-01 (2026-11-18)

Seat: oo-spec-2 (Deploy). Host: `azureuser@172.174.232.254`
(Ubuntu 24.04.5 LTS; passwordless sudo). Chief-routed follow-up to
`azure-vm-deploy-2026-11-18.md`. Scope: issue the origin cert for
`pynescript.online` + `www.pynescript.online` via certbot DNS-01.
NOT done, by design: nginx untouched (read-only at most), no nginx
install/reload, no DNS changes other than the throwaway probe, zone SSL
mode NOT changed.

## 1. cf.ini (local + VM)

`~/.zshrc` sourced in a subshell; `dns_cloudflare_api_token` written to
`/tmp/opencode/cf.ini` mode 600 (81 bytes). Never printed. scp'd to the VM
as `/home/azureuser/cf.ini`, chmod 600 there too. Token never appeared in
command output.

## 2. Scope probe (write + immediate cleanup)

- POST `/client/v4/zones/3b6f8dd01530ad6f65decffb47fba19f/dns_records`
  TXT `_probe-1795039026.pynescript.online` = `probe ok` → **success**
  (record id 837050a13a223da0c1232ffb8ec7115d).
- DELETE same record id → **success**.
- GET `?type=TXT&name=_probe-1795039026.pynescript.online` →
  `result_info.count = 0` (verified gone).
- Zone:DNS:Edit confirmed. No other DNS records touched.

## 3. Install path (VM)

`sudo apt-get update && sudo apt-get install -y python3-certbot-dns-cloudflare`
succeeded; `python3-certbot-dns-cloudflare 2.0.0-1` (+ `python3-cloudflare
2.11.1-1ubuntu1`) from the noble archive. **apt path used; pip fallback NOT
needed.** (Pre-existing `certbot` 2.9.0 / `python3-certbot-nginx` from the
fresh-deploy step remain untouched.)

## 4. Issuance

```
sudo certbot certonly --non-interactive --agree-tos -m ops@hoox.sh \
  --dns-cloudflare --dns-cloudflare-credentials /home/azureuser/cf.ini \
  --dns-cloudflare-propagation-seconds 30 \
  -d pynescript.online -d www.pynescript.online
```

→ "Successfully received certificate." Saved at
`/etc/letsencrypt/live/pynescript.online/fullchain.pem` (privkey at
`.../privkey.pem`). Certbot registered the account and set up its scheduled
renewal task. No secrets in output.

## 5. Verification (VM)

`sudo ls -l /etc/letsencrypt/live/pynescript.online/`:

```
README           (root, 692 B)
cert.pem   -> ../../archive/pynescript.online/cert1.pem
chain.pem  -> ../../archive/pynescript.online/chain1.pem
fullchain.pem -> ../../archive/pynescript.online/fullchain1.pem
privkey.pem   -> ../../archive/pynescript.online/privkey1.pem
```

`sudo openssl x509 -in .../fullchain.pem -noout -subject -issuer -dates`:

```
subject=CN = pynescript.online
issuer=C = US, O = Let's Encrypt, CN = YE2
notBefore=Nov 18 20:59:33 2026 GMT
notAfter=Feb 16 20:59:32 2027 GMT
```

`-text | grep -A1 'Subject Alternative Name'`:

```
X509v3 Subject Alternative Name:
    DNS:pynescript.online, DNS:www.pynescript.online
```

## 6. Cleanup

- `sudo shred -u /home/azureuser/cf.ini` on VM → confirmed
  `ls: cannot access '/home/azureuser/cf.ini': No such file or directory`.
- Local `rm -f /tmp/opencode/cf.ini` → confirmed gone; probe response
  scratch files (`probe_create.json`, `probe_delete.json`, `probe_verify.json`)
  also removed.

## 7. Zone SSL mode (READ-ONLY, not changed)

`GET /zones/3b6f8dd01530ad6f65decffb47fba19f/settings/ssl` →
`{"id": "ssl", "value": "strict", "modified_on": "2026-11-05T19:15:23.874336Z",
"certificate_status": "active", "validation_errors": [], "editable": true}`.

**Already `strict`** (Full strict) with an active certificate — no operator
flip needed for the edge side. Origin now also presents a publicly trusted
LE cert, so strict mode is consistent end to end once nginx is wired.

## Not done / open

- nginx: still not installed, not reloaded, no config applied. Origin is
  still not serving TLS on the VM despite the cert being in place. The
  `deploy/nginx-pynescript.conf` from the deploy step references this
  exact cert path and still awaits the operator's go-ahead.
- DNS: only the throwaway probe TXT was created/deleted; no other records
  touched.
- Renewal: checked `/etc/letsencrypt/renewal/pynescript.online.conf` on the
  VM — it contains `authenticator = dns-cloudflare` and
  `dns_cloudflare_credentials = /home/azureuser/cf.ini`. That file was
  shredded per this task's cleanup step, so the certbot timer will NOT be
  able to renew unattended as-is. Needs an operator decision before ~2027-02
  (or a manual re-run with credentials re-supplied). Flagged, not acted on.
