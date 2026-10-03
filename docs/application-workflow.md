# Application workflow

1. Create or select the correct company. Normalization finds candidates but does
   not automatically merge similar company names.
2. Capture a lead with source and source URL, description, role and available job
   identifiers. The lead can remain unclassified and need never be applied to.
3. Review fit against application rules. Choose technical vs product by the actual
   responsibilities, not a single keyword. Record a reason for the recommendation.
4. Check duplicates. Exact identity matches block a new application; ambiguous
   company/role matches need human review. Different real openings are allowed.
5. Create an application with an explicit resume and application method. The lead
   becomes converted; both changes and their events share one transaction.
6. Prepare the application. User approvals are explicit. Audit history is retained.

## Email

Create an email-method application, then compose an email draft. Use a specific,
human voice and supported experience ([style guide](email-style.md)). Review the
correct recipient, job-specific text and chosen resume link. Save changes, mark
reviewed, then approve. Editing content after review resets it to draft.

There is no Send button or sending endpoint. After sending personally outside the
app, use the draft status `sent` to **record** that fact. Only an approved draft can
be recorded sent; it updates the application's applied timestamp and records an
event. A sent draft cannot be edited. Failures can be recorded and returned to
draft for another review. Cancellation does not delete history.

## Portal / platform / referral

Create the appropriate application. The user carries out the external steps,
then records `applied` with applied_at and an external ID if available. Future
Portal Agent work will retrieve form values from `/profile`, choose an explicitly
approved resume, and request submission approval. No portal is opened or submitted
by this code.

## History and follow-up

Use application PATCH for state changes such as awaiting_response, interview,
rejected, withdrawn or offer. The server adds application_updated events including
previous/current status and changed field names. Use explicit events for recruiter
responses, scheduled interviews and other evidence. Events are not commands.

Application status is a human-maintained ledger, so retrospective correction is
allowed; the audit trail records transitions. A duplicate override is audited.
Changing an application's resume or method requires cancelling outstanding drafts
first, so approved content cannot silently change identity.

## Daily use

Start with the dashboard, capture leads, shortlist opportunities, deliberately
convert them, prepare/review drafts, and update outcomes. List filters are handled
in SQL, not by downloading all records. Profile & Rules stores typed form answers
and matching policy in PostgreSQL. Resume Profiles opens only the supplied public
Drive link on an explicit user click; it never downloads or reads Drive files.
