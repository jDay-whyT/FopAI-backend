# NBU Financial Monitoring & AML Rules
# Source: Law 361-IX (06.12.2019), NBU Resolution 65 (19.05.2020), Resolution 60 (23.03.2022)

## Legal Framework

- **Law 361-IX** — main AML law "On Prevention of Money Laundering"
- **NBU Resolution 65** — rules for banks conducting financial monitoring
- **NBU Resolution 60** — special wartime rules (valid during martial law, expires with martial law)
- **Law 1591-IX** — payment services law

---

## Key Definitions

**Threshold financial operation:** 400,000+ UAH — must be reported to State Financial Monitoring.

**Suspicious transaction:** any amount the bank suspects is money laundering — reported regardless of size.

**PEP (Politically Exposed Person):** senior official, family, associates — enhanced due diligence required.

**Drop:** third party receiving/sending money on behalf of someone else — CRITICAL red flag for banks.

---

## When Bank Must Conduct Verification

**Mandatory triggers (Law 361-IX Art. 11):**
- Any new business relationship
- Transaction 400,000+ UAH
- Wire transfer without full payer info
- Doubt about accuracy of customer data
- Any suspicious transaction regardless of amount

**Enhanced due diligence required for:**
- High-risk customers
- PEPs and their families
- Non-residents from high-risk countries
- Crypto-related operations
- Cash transactions

---

## AML Risk Triggers

**Critical (almost always causes block/request):**
- Receiving funds through third party ("drop") — not direct from payer
- Regular P2P transfers from multiple individuals
- Crypto as income source with P2P conversion to fiat
- No direct contract with actual payer
- Payment purpose does not match FOP KVED
- Transit pattern: money in → immediately transferred out
- FOP receiving payments on personal card instead of FOP account

**Elevated risk:**
- Regular same-amount receipts without clear purpose
- Counterparties from Russia or Belarus (even indirect)
- Non-resident payments without contract
- Payment description: "transfer", "personal", "no VAT"
- Large cash deposits without explanation

**Monitoring triggers:**
- Income inconsistent with declared activity
- Multiple small transactions totaling threshold amount
- New customer with immediately large transactions

---

## What Bank Checks in FOP Operations (Resolution 65)

1. **Who pays** — direct client/platform or third party
2. **Economic purpose** — why this amount, for what service
3. **KVED compliance** — does payment match registered activities
4. **Payment chain** — fiat→crypto→fiat = red flag
5. **Regularity** — systematic income = business activity
6. **Transit pattern** — money in, immediately out = red flag

---

## Bank Request — Document Package

When bank sends economic content request:

**Standard documents:**
1. FOP account bank statement
2. Platform reports (Uber/Bolt/TikTok/Upwork payout statements)
3. Contracts or public offers with clients/platforms
4. Invoices/acts (if available)
5. Explanatory letter (free form)

**Explanatory letter must cover:**
- FOP status and KVED
- Nature of operations (what service, for whom)
- Source of funds (where money originates)
- Why this payment channel
- Why regular (subscription, monthly service, etc.)

**Safe phrases (only if true):**
- "Income from providing services as FOP, KVED [code]"
- "Platform payout per agreement [terms URL]"
- "Payment for advertising services per contract"
- "Regular income from providing [specific service type]"

**Dangerous phrases:**
- "I receive salary through a drop"
- "This is freelance income" (without FOP registration)
- "Personal transfers"
- "Tax optimization"

---

## Crypto Operations

**DPS official position (2024 clarification):**
- Crypto = intangible asset sale
- Tax base = profit (sale price minus documented purchase cost)
- No special crypto tax law — PKU general rules apply
- Individual: 18% PDFO + VZ on profit
- Required docs: exchange CSV, transaction history, KYC screenshot

**Risk levels:**
- Centralized exchange → bank account = LOWER risk
- P2P crypto ↔ fiat = HIGH risk
- Regular P2P from multiple individuals = VERY HIGH risk
- Crypto declared as FOP EP income = NOT ALLOWED (Groups 1-2-3)

**FIFO method:** used in practice for calculating crypto profit (not legally mandated but accepted by DPS in practice).

---

## PRRO (Software Cash Register) Rules (Law 265)

**PRRO required when:**
- Accepting cash payments
- Card payments via POS terminal, QR code, LiqPay, WayForPay, Fondy, Apple Pay, Google Pay
- Selling digital products to individuals with card payment

**PRRO NOT required when:**
- All income via FOP account IBAN (bank transfer)
- PayPal/Wise/Payoneer as platform payouts (not direct retail payment)
- B2B invoicing with bank transfer

**Wartime exemptions:** FOP on Group 1-2 in active combat zones or temporarily occupied territories — exempt from EP and VZ payments.

---

## Finmon Risk Matrix for FOP Types

| FOP Type | Main Risks | Documents Needed |
|----------|-----------|-----------------|
| Taxi driver (Bolt/Uklon) | Transit pattern, personal card | Platform payout report, FOP account statement, KVED 49.32 |
| IT freelancer (Upwork) | Non-resident, Wise/PayPal | Contract, platform statement, KVED |
| Blogger (TikTok/YouTube) | PayPal, irregular amounts | Creator terms, payout CSV, KVED 73.11/63.12 |
| Crypto trader | P2P, no contract | Exchange CSV, transaction history, KYC |
| FOP with employee | Salary structure | Employment contract, payroll records |
| Foreign income (Spain/EU) | Non-resident, drop model | Direct contract with company, FOP account |

---

## Practical Rules for Bot Responses

1. If user mentions "drop" or "third party" payment — HIGH risk, explain clearly
2. If user mentions P2P + crypto — explain bank risk and safe alternatives
3. If user asks about bank request — ask: who pays, FOP or personal account, have contract?
4. Never help construct fake explanations — only truthful ones
5. Always recommend: direct payment from client/platform to FOP IBAN account
6. FOP account ≠ personal card — using personal card for business = compliance problem
7. For any bank block — recommend contacting bank compliance directly with documents
