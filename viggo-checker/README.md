# Viggo → Mail notifikation

Sender dig en mail én gang dagligt, hvis der er nye beskeder i din Viggo-indbakke.

---

## Opsætning (én gang)

### 1. Opret et GitHub repository

1. Gå til [github.com](https://github.com) → **New repository**
2. Giv det et navn, fx `viggo-checker`
3. Sæt det til **Private**
4. Klik **Create repository**

Upload disse filer til repositoriet:
- `checker.py`
- `requirements.txt`
- `.github/workflows/check.yml`

---

### 2. Opret et Gmail App Password

Du må **ikke** bruge dit rigtige Gmail-kodeord — du skal oprette et særligt app-kodeord:

1. Gå til [myaccount.google.com/security](https://myaccount.google.com/security)
2. Sørg for at **2-trins-bekræftelse** er slået til
3. Gå til [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Vælg **Mail** og **Windows-computer** (eller hvad du vil)
5. Klik **Generer** — du får et 16-cifret kodeord. Gem det!

---

### 3. Tilføj dine hemmeligheder til GitHub

1. Gå til dit repository → **Settings** → **Secrets and variables** → **Actions**
2. Klik **New repository secret** og tilføj disse 5 hemmeligheder:

| Navn | Indhold |
|------|---------|
| `VIGGO_USERNAME` | Dit Viggo brugernavn (fx din email) |
| `VIGGO_PASSWORD` | Dit Viggo kodeord |
| `GMAIL_SENDER` | Din Gmail-adresse (fx `dig@gmail.com`) |
| `GMAIL_APP_PASSWORD` | Det 16-cifrede app-kodeord fra trin 2 |
| `GMAIL_RECEIVER` | Den mail du vil modtage notifikationer på |

---

### 4. Test det

1. Gå til **Actions** i dit repository
2. Klik på **Tjek Viggo indbakke**
3. Klik **Run workflow** → **Run workflow**
4. Se om det kører grønt ✅

---

## Hvornår kører det?

Automatisk **hver dag kl. 07:00** dansk tid (sommertid: 09:00 lokal = 07:00 UTC).

Du kan justere tidspunktet i `.github/workflows/check.yml` ved at ændre cron-linjen:
- `0 6 * * *` = 07:00 dansk (vinter) / 08:00 (sommer)
- `0 5 * * *` = 06:00 dansk (vinter)

---

## Fejlfinding

**Ingen mail, selvom der er nye beskeder:**
- Tjek at dine Secrets er tastet rigtigt ind
- Kør workflowet manuelt og se loggen under Actions

**Login fejler:**
- Prøv at logge ind manuelt på Viggo og tjek at brugernavn/kodeord er korrekt

**Gmail afviser forbindelsen:**
- Kontrollér at du bruger App Password og ikke dit rigtige kodeord
- Kontrollér at 2-trins-bekræftelse er slået til på din Google-konto
