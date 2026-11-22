# pynescript.online 525 — read-only diagnostics (2026-11-19 UTC)
Seat: oo-spec-2 (Deploy). Target: Azure VM 172.174.232.254 (pynescript.online).
Mode: READ-ONLY. No NSG/VM/firewall/DNS/CF changes. Nothing applied; recommendations only.
Public IP matches the quoted 172.174.232.254 — no mismatch.

## Symptom
- curl -4 https://pynescript.online/health   -> HTTP/2 525 (server: cloudflare, cf-ray ...-FRA)
- curl -4 https://www.pynescript.online/health -> HTTP/2 525
- curl -4 http://pynescript.online/          -> 301 (edge, unchanged)
- Public DNS now returns Cloudflare proxy IPs (172.66.41.36 / 172.66.42.220; AAAA 2606:4700:3108::ac42:2adc/2adc).
  Board records the site was DNS-only (grey cloud) on 2026-11-18 when it returned 200.

## Origin (this VM) is healthy
- ssh azureuser@172.174.232.254 OK; uptime 18d; load ~0.3.
- ss -tlnp: 80/443 on 0.0.0.0 and [::]; api/datafeed/mcp on loopback (5002/5003/5004).
- Host firewall: ufw inactive; iptables INPUT policy ACCEPT; docker chains normal;
  only fail2ban sshd set (port 22). nginx -t OK.
- Direct HTTPS from outside: curl -k https://172.174.232.254/health -> 200 (SNI=pynescript.online and SNI=www both handshake OK).
- Served cert = Cloudflare Origin CA (SAN *.pynescript.online, pynescript.online; notBefore 2026-11-19 02:56 GMT, notAfter 2041; chain length 1; issuer "CloudFlare Origin SSL Certificate Authority").
  LE cert dir /etc/letsencrypt/live/* is GONE; /etc/ssl/cloudflare/{crt,key} installed 2026-11-19 (VM local 11:11).
- nginx error.log: no SSL/handshake entries. access.log last 3386 reqs (19/Nov): ZERO from Cloudflare edge ranges — CF traffic never reaches nginx.
- Direct 443 reachable from arbitrary ASNs (my egress 92.209.187.117, plus logged scanners 46.151.x, 94.102.x, 195.96.x, 176.120.x, 194.195.x).
- Port 80 direct: timed out from my egress (may be ISP blocking egress :80; could not verify otherwise; not implicated in 525).

## az / Azure control plane: NOT AVAILABLE
- `az account list` -> [] ("Please run az login"). azureProfile.json = {"subscriptions": []}.
- MSAL cache token (only one, tenant f8cdef31-a31e-4b4a-93e4-5f571e91255a, aud management.core.windows.net):
  acquired 2026-11-19 03:49 UTC, expired 05:09 UTC. Read-only ARM GETs with it: /subscriptions -> 0; /tenants -> Default Directory a933872e-0012-4a90-8c1f-e5cabc6c122e (AAD, DE).
- The Azure login never landed in a tenant that exposes any subscription to this account, so steps 1-8 of the requested checklist (VM show, NSG list, effective rules, PIP, etc.) could NOT be executed. No VM/NSG/IP config was read via Azure APIs.
- Requires operator: either re-run login scoped to the correct tenant (Default Directory a933872e-...) or confirm which tenant holds the subscription. Login action is operator-only.

## Root-cause assessment (evidence-based)
CF edge returns 525 = handshake CF->origin failed. But:
  (a) origin handshake works from arbitrary external vantage points (this machine + logged randoms);
  (b) ZERO Cloudflare-edge source IPs appear in nginx access.log (any time, 3386 reqs checked);
  (c) zero TLS handshake errors in nginx error.log;
  (d) host firewall does not filter inbound 80/443.
So CF traffic is not reaching, or not completing TCP/TLS with, 172.174.232.254. Combined with the timing (site flipped to proxied + Origin CA cert installed ~2026-11-19 02:56-11:11, breaking shortly before this report), the likely cause is on the CLOUDFLARE zone side, not the VM:
  1. Zone origin record (A/AAAA/CNAME) does not point at 172.174.232.254 (stale/wrong target, or an AAAA record for an IPv6 the VM does not have — VM has NO global IPv6), and/or
  2. CF->origin blocked between FRA edge and origin by an Azure NSG/firewall rule that permits other sources but not (all) CF ranges — NOT verifiable without az access to the NSG.
SSL mode mismatch (e.g. not Full(strict) vs Origin-CA cert) is UNLIKELY to be the sole cause: with a valid Origin CA cert, Full or Full(strict) handshakes succeed and would appear in nginx logs as connections (none appear). It would also not explain zero CF hits.
NOTE: if the operator flipped the record back to grey-cloud (DNS-only) to "fix" this, browsers would then see the Origin CA cert and reject it — the LE cert it replaced is deleted. Direct-serving is currently broken too unless the cert situation is reverted.

## What would confirm (no changes made)
1. CF dashboard -> pynescript.online zone -> DNS: verify A/AAAA/CNAME for @ and www point at 172.174.232.254 only (delete stale AAAA). Check SSL/TLS mode = Full (strict) with Always Use HTTPS; check "Authenticated Origin Pulls" is off or that origin trusts CF client cert (origin currently serves without client-cert requirements — fine).
2. Azure portal/CLI -> VM NSG (and subnet NSG): inbound 443 (and 80) from Internet/Cloudflare ranges not denied; NIC NSG effective rules for the VM NIC.
3. If (1) is correct and (2) is clean, capture one CF->origin attempt with nginx debug log or tcpdump on :443 to see the SYN/ClientHello.

## Recommended fix (NOT applied — operator decision)
1. Point the zone's apex + www records at 172.174.232.254 only (A record; remove any AAAA that has no routed v6 on the VM), SSL/TLS mode Full (strict) — the Origin CA cert already on disk is correct for this mode. Purge nothing; 525 clears within minutes Once DNS/mode is right.
2. Verify from outside: curl -4 https://pynescript.online/health -> 200 and cf-ray shows FRA; confirm nginx access.log shows the CF edge IPs hitting 200.
3. If still 525 after (1): check NSG inbound rules for 443 (add allow for CF ranges if missing) — needs az/portal (operator).
4. Before any future grey-cloud revert: restore/reissue the LE cert (it was deleted; renewal also broken — cf.ini was shredded; /etc/letsencrypt gone) or expect browser cert errors on direct visits.
5. Re-login az with --tenant a933872e-0012-4a90-8c1f-e5cabc6c122e for any further Azure reads; the logged-in tenant f8cdef31 shows 0 subscriptions to this account.

## Also observed (not actioned)
- /etc/letsencrypt removed; LE renewal path broken (cf.ini shredded earlier by design).
- nginx access.log shows repeated /mcp and /.env probes denied by rule (benign, expected).
- /etc/ssl/cloudflare key is 600 root — fine.
- Public HTTP :80 blocked/timed out from this egress; not conclusive either way (ISP egress filter possible).
