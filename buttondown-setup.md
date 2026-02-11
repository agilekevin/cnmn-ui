# Buttondown Setup Guide for cnmn

Checklist for finishing the [Buttondown](https://buttondown.com) account setup for `cnmn`.

## Account Settings

- [ ] **Username**: `cnmn`
- [ ] **Newsletter name**: `cnmn`
- [ ] **Description**:
  > A free daily synonym puzzle. Each morning you get six clues — find the synonym, decode the consonant code, and share your score. New puzzle every day at cnmn.app.

## Branding

- [ ] **Tint color**: `#6b3410` (the warm brown used throughout the site)
- [ ] **Icon / Avatar**: Use the site favicon or a simple "cnmn" wordmark. Upload at **Settings → Design → Logo**.

## RSS-to-Email (Automated Sends)

This connects the RSS feed so Buttondown sends a new email whenever a puzzle is published.

1. Go to **Settings → Automations → New Automation**
2. Set trigger to **RSS feed**
3. Enter the feed URL: `https://cnmn.app/feed.xml`
4. Configure the email subject template, e.g.: `{{ entry.title }}`
5. Set the send schedule (Buttondown checks the feed periodically; new items trigger a send)
6. Activate the automation

## Verification

- [ ] Send a test email to yourself to confirm formatting
- [ ] Verify the tint color renders correctly in the email header
- [ ] Confirm RSS automation fires when a new puzzle appears in the feed
