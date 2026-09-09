// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: conversation_inbox_tour
 *
 * The regression guard the GTD inbox went without (task #3965).
 *
 * Two autonomous build cycles shipped this feature with the viewer
 * unusable, and the Python suite passed both times, because the failures
 * were not reachable from Python at all: the triage buttons were dead
 * (an inline `doAction` dict carried `view_mode` where the client action
 * schema wants `views`, so every dialog silently failed to open), and the
 * composer's dialog only rendered fields the wizard model happened to
 * expose. Nothing short of clicking the real UI can see either.
 *
 * So the steps below deliberately favour *wiring* over presentation:
 *
 *  - the client action mounts and browse_page's rows reach the DOM;
 *  - expanding a row round-trips fetch_envelope and renders the body;
 *  - Next/Previous actually page (the sequence-window paging behind them
 *    is what made a real mailbox usable);
 *  - each triage button opens its dialog -- the dead-button class of bug;
 *  - the composer opens PREFILLED (subject and quoted original), which is
 *    the part that only exists if default_get ran against the transport;
 *  - the attachments widget sits in the dialog footer, not below the body
 *    editor where it falls under the fold on any real message.
 *
 * Server data and the IMAP stubs are seeded by TestConversationInboxTour
 * in tests/test_conversation_inbox_tour.py -- the transport never touches
 * a socket, so the subjects and body text asserted here come from that
 * fixture.
 */
import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("conversation_inbox_tour", {
  url: "/odoo/action-conversation_inbox.conversation_inbox_client_action",
  steps: () => [
    {
      content: "The inbox client action mounts",
      trigger: ".o_conversation_inbox",
    },
    {
      content: "browse_page's first page reached the DOM",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message A')",
    },
    // --------------------------------------------------------------
    // Paging: the Next/Previous wiring over sequence-window paging.
    // --------------------------------------------------------------
    {
      content: "Page forward",
      trigger: ".o_conversation_inbox button:contains('Next'):not(:disabled)",
      run: "click",
    },
    {
      content: "Page 2 shows its own item",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message C')",
    },
    {
      content: "Page back",
      trigger: ".o_conversation_inbox button:contains('Previous'):not(:disabled)",
      run: "click",
    },
    {
      content: "Page 1 is back",
      trigger: ".o_conversation_inbox_list .card-header:contains('Tour Message A')",
      run: "click",
    },
    // --------------------------------------------------------------
    // Expanding round-trips fetch_envelope.
    // --------------------------------------------------------------
    {
      content: "The envelope body rendered",
      trigger: ".o_conversation_inbox_body:contains('the quote you asked for')",
    },
    {
      content: "Attachment names are listed without being ingested",
      trigger: ".o_conversation_inbox_attachments:contains('quote.pdf')",
    },
    // --------------------------------------------------------------
    // The dead-button regression: every triage action must open its
    // dialog.
    // --------------------------------------------------------------
    {
      content: "Capture opens the capture wizard",
      trigger: ".card-body button:contains('New Conversation')",
      run: "click",
    },
    {
      content: "The capture dialog is up",
      trigger: ".modal footer button:contains('Capture')",
    },
    {
      content: "Dismiss the capture dialog",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "Reassign opens its wizard",
      trigger: ".card-body button:contains('Reassign')",
      run: "click",
    },
    {
      content: "The reassign dialog is up",
      trigger: ".modal footer button:contains('Reassign')",
    },
    {
      content: "Dismiss the reassign dialog",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    // --------------------------------------------------------------
    // The composer: opens, and opens PREFILLED.
    // --------------------------------------------------------------
    {
      content: "Reply opens the composer",
      trigger: ".card-body button:contains('Reply')",
      run: "click",
    },
    {
      content: "The composer dialog is up",
      trigger: ".modal .o_form_view .o_field_widget[name='body']",
    },
    {
      content: "Subject came back prefixed, not empty",
      trigger:
        ".modal .o_field_widget[name='subject'] input:value(/^Re: Tour Message A$/)",
    },
    {
      content: "The recipient was taken from the original's sender",
      trigger:
        ".modal .o_field_widget[name='to_emails'] input:value(/tourist@example.com/)",
    },
    {
      content: "The original is quoted into the editable body",
      trigger:
        ".modal .o_field_widget[name='body']:contains('the quote you asked for')",
    },
    {
      // The UX fix: below the body editor this control sits under
      // the fold on a message of ordinary length, so attaching a
      // file means scrolling past the whole draft first.
      content: "The attachments control is in the footer, not under the body",
      trigger: ".modal footer .o_field_widget[name='attachment_ids']",
    },
    {
      // Same reasoning: whether the exchange is kept in Odoo is a
      // decision about the message being written, so it must be
      // visible while writing it rather than below the editor.
      content: "The filing toggle is above the body, not under it",
      trigger:
        ".modal .o_inner_group:has(.o_field_widget[name='subject']) .o_field_widget[name='file_in_odoo']",
    },
    {
      content: "Close the composer",
      trigger: ".modal footer button:contains('Cancel')",
      run: "click",
    },
    {
      content: "Back on the inbox with no dialog left open",
      trigger: ".o_conversation_inbox:not(:has(.modal))",
    },
  ],
});
