When Odoo sends a notification email to multiple recipients (e.g., a customer
plus a salesperson on an order confirmation), each individual delivery shows
only the recipient's own address in the ``To`` header. Other recipients are
invisible to the email client.

This module rewrites the ``Cc`` display header so every recipient can see who
else was notified — without changing the SMTP envelope. Delivery remains
per-recipient: each person still receives their own copy, with their own
tracking pixel, portal link, and per-partner unsubscribe URL intact.

## Behaviour

- **Source of CC addresses**: all partners listed in
  ``mail.message.notified_partner_ids`` for the thread message that triggered
  the notification, minus the message author.
- **SMTP envelope unchanged**: ``email_to_normalized`` (the ``RCPT TO`` list)
  is never modified. The Cc header is display-only.
- **Mass-mailing excluded**: records with a ``mailing_id`` are never touched.
- **Single-recipient sends**: if fewer than two partners were notified, no Cc
  header is added (nothing to show).
- **Composer compatibility**: works alongside ``mail_composer_cc_bcc`` — any
  Cc partners set manually in the mail composer are preserved and deduplicated
  against the auto-computed set.

## Privacy note

Every non-author notified partner will see every other notified partner's
display name and email address in their Cc header. This is intentional and
mirrors standard email etiquette. If a partner should not appear in Cc, remove
them from the thread's notification list via the message-subtype or follower
settings — no extra configuration flag is needed.
