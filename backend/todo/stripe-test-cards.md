# Stripe Test Cards Reference

All cards use any future expiry (e.g. `12/34`) and any 3-digit CVC.
ZIP code: any 5-digit number (e.g. `12345`).

## Basic Payment Outcomes

| Scenario                  | Card Number          | Result                        |
|---------------------------|----------------------|-------------------------------|
| Payment succeeds          | 4242 4242 4242 4242  | `checkout.session.completed`  |
| Payment declined          | 4000 0000 0000 9995  | Checkout shows decline error  |
| Insufficient funds        | 4000 0000 0000 9995  | Checkout shows decline error  |
| Card expired (issuer)     | 4000 0000 0000 0069  | Checkout shows card_expired   |
| Incorrect CVC             | 4000 0000 0000 0127  | Checkout shows incorrect_cvc  |
| Processing error          | 4000 0000 0000 0119  | Checkout shows processing_error|

## 3D Secure (Strong Customer Authentication)

| Scenario                              | Card Number          |
|---------------------------------------|----------------------|
| 3DS required, then succeeds           | 4000 0027 6000 3184  |
| 3DS required, then fails              | 4000 0084 0000 1629  |
| 3DS optional, card holder not enrolled| 4000 0000 0000 3220  |

For 3DS cards: Stripe shows an auth challenge modal. Click "Complete" to simulate success
or "Fail" to simulate failure.

## Subscription-Specific Scenarios

| Scenario                            | Card Number          | Notes                             |
|-------------------------------------|----------------------|-----------------------------------|
| Succeeds now, fails on renewal      | 4000 0000 0000 3220  | Use to test dunning / past_due    |
| Always succeeds                     | 4242 4242 4242 4242  | Renewals also succeed              |
| Requires auth on every payment      | 4000 0027 6000 3184  | SCA — every renewal needs auth    |

## Debit Cards

| Scenario              | Card Number          |
|-----------------------|----------------------|
| Visa debit succeeds   | 4000 0566 5566 5556  |
| Mastercard debit      | 5200 8282 8282 8210  |

## International Cards

| Country | Card Number          |
|---------|----------------------|
| UK      | 4000 0082 6000 0000  |
| Canada  | 4000 0012 4000 0000  |
| Germany | 4000 0027 6000 0016  |
| India   | 4000 0035 6000 0008  |

## PaymentMethods Beyond Cards (available in test mode)

| Method          | How to trigger                                                   |
|-----------------|------------------------------------------------------------------|
| SEPA Direct     | Use email `test@example.com` and IBAN `DE89370400440532013000`  |
| iDEAL           | Select iDEAL on checkout, pick any bank, click "Authorize"       |
| Bancontact      | Select Bancontact, complete the test flow                        |

> Note: The ecalt checkout is currently card-only (`mode="subscription"`).
> To enable other payment methods, update `stripe.checkout.Session.create()`
> in `subscriptions.py:L100` to add `payment_method_types`.

## Testing Webhooks Directly (no browser needed)

```bash
# Fire a successful checkout event
stripe trigger checkout.session.completed

# Fire subscription events
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted

# List all triggerable events
stripe trigger --help
```

## Quick Reference: What the ecalt webhook handles

From `subscriptions.py:L126-L154`:

| Event                              | Handler action                                     |
|------------------------------------|----------------------------------------------------|
| `checkout.session.completed`       | `upsert_subscription_from_stripe()` — creates row  |
| `customer.subscription.updated`    | `UPDATE subscriptions SET status = ...`            |
| `customer.subscription.deleted`    | `UPDATE subscriptions SET status = ...`            |
