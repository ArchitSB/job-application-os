export const sources = [
  "linkedin",
  "telegram",
  "naukri",
  "wellfound",
  "hnhiring",
  "unstop",
  "company_portal",
  "referral",
  "email",
  "other",
];
export const resumes = ["technical", "product"];
export const methods = ["email", "portal", "platform", "referral", "other"];
export const statuses: Record<string, string[]> = {
  leads: [
    "discovered",
    "reviewing",
    "shortlisted",
    "rejected",
    "duplicate",
    "approved",
    "converted",
    "expired",
  ],
  applications: [
    "discovered",
    "shortlisted",
    "approved",
    "prepared",
    "applied",
    "awaiting_response",
    "interview",
    "rejected",
    "withdrawn",
    "offer",
    "skipped",
  ],
  "email-drafts": [
    "draft",
    "reviewed",
    "approved",
    "sent",
    "failed",
    "cancelled",
  ],
};
export const titles: Record<string, string> = {
  dashboard: "Dashboard",
  leads: "Leads",
  applications: "Applications",
  companies: "Companies",
  contacts: "Contacts",
  "email-drafts": "Email Drafts",
  resumes: "Resume Profiles",
  settings: "Profile & Rules",
};
export type Field = {
  key: string;
  title: string;
  type?:
    | "text"
    | "textarea"
    | "email"
    | "url"
    | "number"
    | "datetime-local"
    | "company"
    | "application"
    | "lines";
  options?: string[];
  required?: boolean;
};
const company: Field = {
  key: "company_id",
  title: "Company",
  type: "company",
  required: true,
};
const role: Field = { key: "role_title", title: "Role title", required: true };
const notes: Field = { key: "notes", title: "Notes", type: "textarea" };
const urls: Field[] = [
  { key: "job_url", title: "Job URL", type: "url" },
  { key: "application_url", title: "Application URL", type: "url" },
  { key: "source_url", title: "Source URL", type: "url" },
];
const contact: Field[] = [
  { key: "contact_name", title: "Contact name" },
  { key: "contact_email", title: "Contact email", type: "email" },
];
export const fields: Record<string, Field[]> = {
  companies: [
    { key: "name", title: "Company name", required: true },
    { key: "domain", title: "Domain (e.g. example.com)" },
    { key: "website", title: "Website", type: "url" },
    { key: "linkedin_url", title: "LinkedIn URL", type: "url" },
    notes,
  ],
  leads: [
    company,
    role,
    { key: "source", title: "Source", options: sources, required: true },
    { key: "location", title: "Location" },
    { key: "employment_type", title: "Employment type" },
    ...urls,
    { key: "description", title: "Job description", type: "textarea" },
    {
      key: "requirements",
      title: "Requirements (one per line)",
      type: "lines",
    },
    { key: "raw_post_text", title: "Original post", type: "textarea" },
    ...contact,
    { key: "posted_at", title: "Posted at", type: "datetime-local" },
    { key: "salary_text", title: "Salary information" },
    { key: "external_job_id", title: "External job ID" },
    { key: "category", title: "Category" },
    {
      key: "recommended_resume_type",
      title: "Recommended resume (optional)",
      options: resumes,
    },
    { key: "fit_score", title: "Fit score (0–100)", type: "number" },
    { key: "fit_reason", title: "Fit rationale", type: "textarea" },
  ],
  applications: [
    company,
    role,
    {
      key: "application_method",
      title: "Application method",
      options: methods,
      required: true,
    },
    {
      key: "resume_type",
      title: "Resume profile — choose deliberately",
      options: resumes,
      required: true,
    },
    { key: "source", title: "Source", options: sources, required: true },
    ...urls,
    ...contact,
    { key: "external_job_id", title: "External job ID" },
    { key: "external_application_id", title: "External application ID" },
    { key: "applied_at", title: "Applied at", type: "datetime-local" },
    notes,
  ],
  contacts: [
    { ...company, required: false },
    { key: "name", title: "Full name", required: true },
    { key: "email", title: "Email", type: "email" },
    { key: "title", title: "Role / title" },
    { key: "linkedin_url", title: "LinkedIn URL", type: "url" },
    notes,
  ],
  "email-drafts": [
    {
      key: "application_id",
      title: "Application (email method only)",
      type: "application",
      required: true,
    },
    {
      key: "recipient_email",
      title: "Recipient email",
      type: "email",
      required: true,
    },
    { key: "recipient_name", title: "Recipient name" },
    {
      key: "resume_type",
      title: "Resume profile",
      options: resumes,
      required: true,
    },
    { key: "subject", title: "Subject", required: true },
    { key: "body", title: "Email body", type: "textarea", required: true },
  ],
};
export const columns: Record<string, string[]> = {
  leads: [
    "role_title",
    "company_name",
    "source",
    "status",
    "recommended_resume_type",
    "discovered_at",
  ],
  applications: [
    "role_title",
    "company_name",
    "status",
    "resume_type",
    "application_method",
    "applied_at",
  ],
  companies: ["name", "domain", "website", "created_at"],
  contacts: ["name", "email", "title", "created_at"],
  "email-drafts": [
    "subject",
    "recipient_email",
    "resume_type",
    "status",
    "updated_at",
  ],
};
