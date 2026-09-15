# India Trading Bot - Setup Guide

Your project path: `D:\work\india-trading-bot`

---

## Your current setup (saved)


| Setting          | Value                                                                               |
| ---------------- | ----------------------------------------------------------------------------------- |
| Capital          | Rs 1,00,000                                                                         |
| Income target    | ~Rs 6,000/month (if backtest pattern holds)                                         |
| Email reports    | Optional SMTP in `.env`                                                           |
| Broker (planned) | Zerodha Kite Connect Personal (free)                                              |
| Review period    | 1 month paper trading before live                                                   |
| Trading mode     | **DRY RUN** (`LIVE_TRADING=false`)                                                  |


---

## One-time install

Double-click `**setup.bat`** or run:

```powershell
cd D:\work\india-trading-bot
pip install -r requirements.txt
python check_setup.py
```

---

## Daily use (now - paper trading month)


| Task                             | Command                                  |
| -------------------------------- | ---------------------------------------- |
| Check setup                      | `python check_setup.py`                  |
| Paper trade                      | `python run_paper.py`                    |
| Backtest                         | `python run_backtest.py`                 |
| Analysis + email                 | `python run_monthly_analysis.py --email` |
| Test order flow (no real trades) | `python run_live.py --force`             |


Scheduled automatically:

- **09:15** - Morning email report (`run_report.bat`)
- **21:15** - Evening email report (`run_report.bat`)

---

## Markets & strategies


| Market               | Strategy          | Timeframe | NSE symbol |
| -------------------- | ----------------- | --------- | ---------- |
| Vedanta Aluminium    | Mean reversion    | 15m       | VAML       |
| Vedanta              | Momentum breakout | 1h        | VEDL       |
| Vedanta Power        | Momentum breakout | 1h        | VEDPOWER   |
| Vedanta Iron & Steel | Trend following   | 4h        | VISL       |
| BHEL                 | Trend following   | 4h        | BHEL       |


Vedanta demerged names (VAML, VEDL, VEDPOWER, VISL) share a correlation filter — only one long at a time.

---

## After 1 month - go live with Zerodha

### Step 0: Open a Zerodha account (for transactions)

If you don't already have a Zerodha trading account, open one first — this is the account the bot places real orders through.

1. Sign up at [https://zerodha.com/open-account/](https://zerodha.com/open-account/)
2. Complete KYC (PAN, bank details, e-sign). This usually takes 1-2 working days.
3. Once approved, log in at [https://kite.zerodha.com/](https://kite.zerodha.com/) — this is the trading terminal the bot connects to.
4. Fund the account (UPI / net banking) so there is margin available for orders.

> The bot uses **Kite Connect** (Zerodha's API). You need a Zerodha account first; the API key is issued against that account.

### Step 1: Kite Connect subscription

1. Go to [https://developers.kite.trade/](https://developers.kite.trade/)
2. Create a Kite Connect app — **Personal (free)** or paid Connect (₹500/month for market data)
3. Set redirect URL: `http://127.0.0.1:8000/`

**How the login works** (see [Kite Connect user docs](https://kite.trade/docs/connect/v3/user/)):

1. The bot opens the Kite login page with your `api_key`.
2. You log in; Kite redirects back with a one-time `request_token`.
3. The bot exchanges that token (plus a checksum) for an `access_token`.
4. The `access_token` signs every order/portfolio request. It expires daily at 6:00 AM IST, so the bot re-logs-in each morning (automated via TOTP).

> **Redirect URL note:** The agent API (`run_agent_api.py`, port 8000) serves a public callback at `/` and `/kite-login` that displays the `request_token` after you authorize. So `http://127.0.0.1:8000/` is the correct redirect URL — you'll see the token on that page and can paste it into `run_kite_login.py`.

### Step 2: Add keys to `.env`

```env
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
```

### Step 3: Automated login (TOTP — no browser paste)

Add to `.env`:

```env
ZERODHA_USER_ID=your_client_id
ZERODHA_PASSWORD=your_password
ZERODHA_TOTP_SECRET=base32_from_2fa_setup
```

Then:

```powershell
./scripts/dev.sh login
```

See `docs/SECURITY.md` for boot auto-start and LAN security.

### Step 4: Start small

```powershell
# Still safe - dry run with real prices when keys present
python run_live.py --force

# Real orders (only when ready):
# Set LIVE_TRADING=true in .env
python run_live.py
```

**Recommendation:** Start live with Rs 10,000-25,000, not full Rs 1,00,000.

### Optional: Order status webhooks (Postbacks)

Kite Connect can push order-status updates to your app when an order is `COMPLETE`, `CANCELLED`, `REJECTED`, or `UPDATE`d. This is mainly for platforms that place orders for many users. For a single personal account, the bot polls order status directly, so **you do not need to configure Postbacks**.

If you ever want them, see the [Kite Connect Postbacks docs](https://kite.trade/docs/connect/v3/postbacks/). Each payload includes a `checksum` (SHA-256 of `order_id + order_timestamp + api_secret`) that you must verify to confirm the update really came from Kite Connect.

---

## Configuration file (`.env`)

All secrets live in `.env` (never commit to git - protected by `.gitignore`).


| Variable             | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `SMTP_`* / `EMAIL_*` | Email reports (already set)                     |
| `KITE_API_KEY`       | Zerodha API key                                 |
| `KITE_API_SECRET`    | Zerodha API secret                              |
| `KITE_ACCESS_TOKEN`  | Daily token from `run_kite_login.py`            |
| `LIVE_TRADING`       | `false` = dry run, `true` = real orders         |
| `CASH_ONLY`          | `true` = long-only equity/ETFs (no shorts)      |
| `MAX_DAILY_LOSS`     | Stop trading after this loss (default Rs 2,000) |
| `KILL_SWITCH`        | `true` = halt all trading immediately           |


---

## Safety controls

- **1% stop loss** per trade (ATR-based)
- **Correlation filter** - won't long multiple Vedanta demerged stocks at once
- **Market hours only** for live orders (9:15-15:30 IST)
- **Daily loss limit** - bot stops after `MAX_DAILY_LOSS`
- **Kill switch** - set `KILL_SWITCH=true` in `.env` to halt

---

## Project files

```
run_paper.py              Paper trading
run_backtest.py           Historical backtest
run_monthly_analysis.py   Daily/monthly P&L + email
run_live.py               Zerodha execution (dry-run or live)
run_kite_login.py         Zerodha daily token
check_setup.py            Verify everything is configured
setup.bat                 One-click install + check
run_report.bat            Email report (scheduled)
run_live_dry.bat          Quick dry-run execution

config.py                 Capital, markets, strategy params
.env                      Your secrets (email + kite keys)
data/paper_state.json     Paper portfolio state
data/live_state.json      Live/dry-run portfolio state
data/trading.db           Order history (SQLite)
```

---

## Realistic expectations (Rs 1L capital)


| Metric      | Backtest (60 days) | Longer analysis      |
| ----------- | ------------------ | -------------------- |
| Return      | +12.89%            | Varies by month      |
| Monthly avg | ~Rs 6,400          | ~Rs 500-6,000        |
| Win rate    | 16.4%              | Uneven months normal |


Treat Rs 6,000/month as a **good-month target**, not a salary.

---

## Troubleshooting


| Problem               | Fix                                              |
| --------------------- | ------------------------------------------------ |
| Email not sending     | Check Gmail app password in `.env`               |
| `pip install` fails   | Run `python -m pip install -r requirements.txt`  |
| Kite login fails      | Re-run `run_kite_login.py` (token expires daily) |
| Orders not placing    | Check `LIVE_TRADING=true` and market hours       |
| Short signals skipped | Normal with `CASH_ONLY=true`                     |


Run `python check_setup.py` anytime to see status.