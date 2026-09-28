# CareBridge — Gateway Context

> Handoff document from the **CareBridge application project** (`InternAssignmentShahriar/carebridge-clinic-flow`) to the separate **LiteLLM gateway project** (`InternAssignmentShahriar/carebridge-liteLLM`).
>
> Prepared: 2026-09-28. Based on the repository state at `main` commit `f2a0fc2` plus the documentation files present in the repository at that time.
>
> This document contains **no secrets**. Environment variables are listed by **name only**.

---

## 1. Document Purpose

This document gives the developer (human or AI agent) of `carebridge-liteLLM` enough context to understand CareBridge **without modifying the CareBridge project**.

The gateway developer should read this before doing any work so that they understand:

- what CareBridge is and how it is built,
- where security and business rules live today,
- what the current AI implementation does,
- why the AI architecture is being rebuilt ("AI V2"),
- what LiteLLM **is** responsible for, and — more importantly — what it is **not** responsible for.

The CareBridge repository is the source of truth for implementation details. Where older documentation in the CareBridge repository disagrees with the code, the disagreement is listed in [Section 28](#28-known-documentation--implementation-discrepancies) rather than silently resolved.

Wording conventions used below:

- **Confirmed** — verified in the current repository source.
- **Not confirmed from the current repository.** — the claim may be true in the live Supabase project or deployment, but no code/migration in the repository proves it.

---

## 2. Project Identity

| Item | Value |
| --- | --- |
| Project name | CareBridge — Clinic Appointment & Patient Management |
| Repository (local) | `InternAssignmentShahriar/carebridge-clinic-flow` |
| GitHub repository | `https://github.com/shahriar-rashid-13/carebridge-clinic-flow` (from `project_description_update.md` and `git remote`) |
| Builder tooling | Built with Lovable (`.lovable/project.json`, template `tanstack_start_ts_current`). Commits pushed to `main` sync back to Lovable. |
| Frontend | TanStack Start (React 19) app in `src/` |
| Backend | Supabase (PostgreSQL + Auth + RLS + RPCs + one Edge Function) |
| Production deployment | Vercel, `https://carebridge-clinic-flow.vercel.app/` (from `project_description_update.md`). No `vercel.json` in the repository. |
| Origin | SJ Innovation intern assignment. Assessment 1 = clinic app (`project_description.md`). Assessment 2 = AI features, automations, RAG, tests (`project_description_update.md`). |

Overall purpose: a small clinic system where a **patient** books appointments, a **receptionist** confirms/schedules them and handles billing, and a **doctor** runs consultations and writes prescriptions. Only synthetic test data is used.

Supabase's role: Supabase is the entire backend and the **final source of truth** — database, authentication, row-level security, security-definer RPCs, and the AI Edge Function host.

---

## 3. Product Overview

CareBridge is a clinic appointment and patient-management system with three roles sharing one database.

Central business workflow (confirmed in the provider and route code):

```text
Patient books appointment            -> appointments.status = 'requested'
Receptionist confirms (or reschedules) -> status = 'confirmed'
Doctor opens the confirmed appointment (/consult/$id)
Doctor records diagnosis, medicines, notes -> prescriptions row inserted
Appointment marked                    -> status = 'completed'
Patient views prescription (/prescriptions)
Receptionist creates bill for completed visit -> bills.status = 'unpaid'
Receptionist records payment          -> bills.status = 'paid', payment_method, paid_at
```

Cancellation (`status = 'cancelled'`) is available to patients and receptionists for `requested`/`confirmed` appointments.

Product goal: a calm, role-separated clinic workspace where each role sees only its own sidebar and data, with Supabase RLS as the data-access boundary. Assessment 2 adds an AI assistant and other AI features on top of the same app.

---

## 4. Technology Stack

From `package.json`, `vite.config.ts`, `tsconfig.json`, `components.json`.

### Frontend / framework

| Area | Package / version |
| --- | --- |
| UI library | `react` / `react-dom` `^19.2.0` |
| Meta-framework | `@tanstack/react-start` `1.168.32` (SSR-capable) |
| Router | `@tanstack/react-router` `1.170.18`, file-based routing via `@tanstack/router-plugin` `1.168.23` (generates `src/routeTree.gen.ts`) |
| Server data cache | `@tanstack/react-query` `^5.101.1` (router context carries a `QueryClient`; clinic data itself is **not** fetched through React Query — it lives in `ClinicProvider` state) |
| Language | TypeScript `^5.8.3`, strict mode with `noUncheckedIndexedAccess`, `noPropertyAccessFromIndexSignature`, `exactOptionalPropertyTypes` |
| Build | Vite `8.1.5` via `@lovable.dev/vite-tanstack-config` `2.23.1` (bundles tanstackStart, React plugin, Tailwind, tsconfig paths, and `nitro` for server build) |
| Styling | Tailwind CSS `^4.2.1` (`@tailwindcss/vite`), `tw-animate-css`, `class-variance-authority`, `tailwind-merge`, `clsx` |
| Components | shadcn/ui ("new-york" style, `components.json`) on Radix UI primitives (`@radix-ui/react-*`), files in `src/components/ui/` |
| Icons | `lucide-react` |
| Forms / validation | `react-hook-form`, `@hookform/resolvers`, `zod` (available; not every form uses them) |
| Toasts | `sonner` |
| Markdown (AI replies) | `react-markdown` `^10.1.0` |
| Charts | `recharts` (reports) |
| Dates | `date-fns`, `react-day-picker` |

### Backend

| Area | Detail |
| --- | --- |
| Backend-as-a-service | Supabase via `@supabase/supabase-js` `^2.116.0` |
| Edge Function runtime | Deno (`Deno.serve`, `npm:@supabase/supabase-js@2`) |
| Hosting | Vercel (frontend). `vite.config.ts` comment notes nitro defaults to a Cloudflare target; the actual Vercel build settings are **not confirmed from the current repository**. |

### Tooling

ESLint 9 + `typescript-eslint`, Prettier 3, `bun.lock` and `package-lock.json` both present, `bunfig.toml`.

Scripts: `dev`, `build`, `build:dev`, `preview`, `lint`, `format`. **No test script and no test framework** are present.

### Confirmed NOT used

- No Redux, Zustand, MobX, Jotai, or similar state library. Global state is React Context (`ClinicProvider`) plus a small hand-written external store (`useSyncExternalStore`) for auth.
- No provider AI SDKs (no OpenAI/Gemini/OpenRouter/LiteLLM packages). The Edge Function uses raw `fetch`.
- No `supabase/config.toml` and no Supabase-generated database types in the repository.

---

## 5. Repository Structure

```text
carebridge-clinic-flow/
├── src/
│   ├── routes/                     File-based routes (TanStack Router)
│   │   ├── __root.tsx              Root route: HTML shell, global auth redirect for non-public paths
│   │   ├── index.tsx               Public landing page
│   │   ├── login.tsx               Email/password + Google login
│   │   ├── signup.tsx              Email/password signup + Google
│   │   ├── _authenticated.tsx      Pathless layout: requires session + valid profile, syncs role
│   │   └── _authenticated/         All signed-in screens (see Section 7)
│   ├── components/
│   │   ├── clinic/
│   │   │   ├── app-shell.tsx       Sidebar + top bar; role-specific navigation
│   │   │   ├── carebridge-ai-panel.tsx  AI chat UI (conversations, messages, Edge Function call)
│   │   │   ├── page.tsx, status-badge.tsx, doctor-note.tsx, current-user-card.tsx
│   │   ├── ui/                     shadcn/Radix primitives
│   │   └── theme-toggle.tsx
│   ├── lib/
│   │   ├── auth/store.ts           Supabase Auth session + profile/role store (useAuth)
│   │   ├── clinic/
│   │   │   ├── store.tsx           ClinicProvider / useClinic — data loading + all mutations
│   │   │   ├── adapters.ts         snake_case DB rows -> camelCase UI types
│   │   │   ├── types.ts            UI domain types (Role, Doctor, Appointment, ...)
│   │   │   └── data.ts             Date/money helpers + historic seed data (seed arrays unused by provider)
│   │   ├── supabase/client.ts      Browser Supabase client (publishable key only)
│   │   ├── supabase/test.ts        Connectivity test helper
│   │   └── theme/theme-context.tsx "calm" / "vibrant" theme
│   ├── router.tsx, start.ts, server.ts   TanStack Start entry points (server.ts = SSR error wrapper)
│   └── styles.css
├── supabase/
│   ├── functions/carebridge-ai/
│   │   ├── index-gemini.ts         Current AI Edge Function source (Gemini direct)
│   │   └── model-config-gemini.ts  Provider/model constant
│   └── migrations/                 Only 4 incremental migrations (see Section 10)
├── opinions/                       AI-generated audit/design reports (not authoritative)
├── IMPLEMENTATION_PLAN.md          Status doc dated 2026-09-18 (partly stale)
├── project_description.md          Assessment 1 brief
├── project_description_update.md   Assessment 2 brief
├── kt.md                           Empty file (0 bytes)
└── README.md                       Original Lovable prompt text (stale)
```

---

## 6. Frontend Architecture

### Data flow

```text
Route component (src/routes/_authenticated/*.tsx)
        │  const clinic = useClinic()
        ▼
ClinicProvider  (src/lib/clinic/store.tsx)
        │  React state + async mutation functions
        ▼
Adapter layer  (src/lib/clinic/adapters.ts)   rows <-> UI types
        ▼
Supabase JS client  (src/lib/supabase/client.ts)  with the user's session JWT
        ▼
Supabase PostgREST / RPC  ──►  PostgreSQL + RLS
```

The AI screen is the exception: `carebridge-ai-panel.tsx` talks to Supabase directly (`ai_conversations`, `ai_messages`) and calls the Edge Function via `supabase.functions.invoke("carebridge-ai", ...)`. It does not go through `ClinicProvider`.

### What `ClinicProvider` owns

On sign-in it loads, in parallel, `profiles`, `doctors` (with joined `profile:profiles!doctors_user_id_fkey(id, full_name, email, role)`), `appointments`, `prescriptions`, `bills`. What each role actually receives is whatever RLS returns.

It exposes:

- State: `role`, `currentPatientId` (= `auth.users.id`), `currentDoctorId` (resolved via `doctors.user_id`), `doctors`, `patients` (profiles with `role = 'patient'`), `appointments`, `prescriptions`, `invoices`, `loading`, `error`, `reload()`.
- Lookups: `getDoctor`, `getPatient`, `isSlotTaken` (client-side hint only).
- Mutations: `updatePatientProfile`, `bookAppointment`, `setAppointmentStatus`, `rescheduleAppointment`, `completeConsultation`, `upsertDoctor`, `promotePatientToDoctor` (RPC), `promotePatientToReceptionist` (RPC), `toggleDoctorActive`, `createInvoice`, `markInvoicePaid`.
- A full-screen loading state and a "Clinic data could not be loaded" error state with retry. It does **not** fall back to seed data.

### Important files

| Concern | File |
| --- | --- |
| Clinic store | `src/lib/clinic/store.tsx` |
| Domain types | `src/lib/clinic/types.ts` |
| Row mapping | `src/lib/clinic/adapters.ts` |
| Helpers / historic seed data | `src/lib/clinic/data.ts` |
| Supabase client | `src/lib/supabase/client.ts` |
| Auth/session | `src/lib/auth/store.ts`, `src/routes/__root.tsx`, `src/routes/_authenticated.tsx` |
| AI UI | `src/components/clinic/carebridge-ai-panel.tsx`, `src/routes/_authenticated/ai.tsx` |
| Navigation | `src/components/clinic/app-shell.tsx` |

### Architectural boundaries

- The browser uses only the Supabase URL and **publishable** key plus the user's session. No service-role key exists in frontend code.
- UI role checks are presentation only. Data access is enforced by RLS and security-definer RPCs.
- Several workflows are multi-step writes performed from the browser (see Section 11); they are not transactional.
- The Supabase client (`client.ts`) is created lazily: if `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` are missing, a proxy throws on first use rather than at module load (keeps SSR/prerender from crashing).

---

## 7. Routes and Role Areas

All routes below are confirmed from `src/routes/`. Sidebar items are from `app-shell.tsx`. Each role-specific screen shows a "not available" state when opened by another role.

### Public routes

| Route | Purpose |
| --- | --- |
| `/` | Landing page |
| `/login` | Email/password login, Google login, demo-account email prefill. Requires `redirect` search param (defaults to `/dashboard`). |
| `/signup` | Email/password signup (creates patient via DB trigger — see Section 8), Google signup |

### Shared authenticated routes

| Route | Purpose |
| --- | --- |
| `/dashboard` | Role-specific dashboard (patient / `DoctorDashboard` / `ReceptionDashboard`) |
| `/appointments` | Appointment list; behaviour differs per role (see below) |
| `/ai` | CareBridge AI chat (all three roles see it in the sidebar) |
| `/consult/$id` | Consultation screen; submit disabled unless role is doctor |

### Patient

| Route | Purpose |
| --- | --- |
| `/book` | Pick doctor, date (doctor working days), free slot, reason, notes; creates a `requested` appointment |
| `/appointments` | Own appointments; can cancel `requested`/`confirmed` |
| `/prescriptions` | Own prescriptions (diagnosis, medicines, notes) |
| `/profile` | View and edit own profile (contact, medical history, emergency contact) |
| `/ai` | Patient Assistant (only role with AI tools today) |

### Doctor

| Route | Purpose |
| --- | --- |
| `/schedule` | Own schedule; toggle own active/inactive status |
| `/appointments` | Own appointments; "Consult" button on `confirmed` appointments |
| `/records` | Patient records visible to the doctor |
| `/consult/$id` | Record diagnosis, medications, notes; completes appointment |
| `/ai` | "Clinical Assistant" label — general chat only, **no tools** in current function |

### Receptionist

| Route | Purpose |
| --- | --- |
| `/appointments` | All appointments; Confirm / Reschedule on `requested`; Cancel on `requested`/`confirmed` |
| `/doctors` | Manage doctors: edit details/days/slots/fee/room, toggle active, **promote patient → doctor**, **promote patient → receptionist** |
| `/patients` | Patient directory |
| `/billing` | Completed visits without a bill → create bill; mark bill paid. Only `cash` is selectable; `card` and `insurance` options are present but disabled |
| `/reports` | Clinic metrics |
| `/ai` | "Front Desk Assistant" label — general chat only, **no tools** in current function |

---

## 8. Authentication

Implemented in `src/lib/auth/store.ts` (a module-level store read through `useSyncExternalStore`, exposed as `useAuth()`).

- **Provider:** Supabase Auth.
- **Email/password:** `supabase.auth.signInWithPassword`. Confirmed.
- **Google OAuth:** `supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: origin + redirect } })`. Confirmed in code. Google provider configuration in the Supabase dashboard is **not confirmed from the current repository**.
- **Signup:** `supabase.auth.signUp` with `options.data.full_name`. If Supabase returns a session the user goes to `/dashboard`; otherwise the user is told to confirm email and log in. The code creates **no** profile row itself. `IMPLEMENTATION_PLAN.md` states a database trigger creates a `patient` profile; that trigger is **not confirmed from the current repository** (no migration for it).
- **Session restoration:** `initializeAuth()` calls `supabase.auth.getSession()` once, then subscribes to `onAuthStateChange`. The root route's `beforeLoad` runs this on the client for non-public paths and redirects to `/login` if unauthenticated. During SSR auth is skipped (no cookie-backed session); the client-side `_authenticated` layout resolves it after hydration.
- **Profile lookup / role retrieval:** after any session change, `profiles.select("id, full_name, role").eq("id", session.user.id).single()`. A missing profile or a role outside `patient | doctor | receptionist` produces a `profileError` and a "Your clinic profile is not ready" screen.
- **Role representation:** `profiles.role` text/enum with values `patient`, `doctor`, `receptionist` (TypeScript `Role` type). One role per user.
- **Identity mapping:** `auth.users.id → profiles.id` (confirmed: profile is queried by `id = session.user.id`; `ai_conversations.user_id` and RPCs use `auth.uid()` against `profiles.id`). A doctor additionally has `doctors.user_id → profiles.id`; the app resolves `currentDoctorId` from that.
- **Demo users:** `DEMO_USERS` in `auth/store.ts` only prefill the email field on `/login`. They are not a login bypass.

---

## 9. Roles and Authorization

| Role | Application-level capabilities (from UI + provider) |
| --- | --- |
| patient | Book appointments, view/cancel own appointments, view own prescriptions, edit own profile, use AI patient tools |
| doctor | View own schedule/appointments, view patient records, run consultations, write prescriptions, toggle own active status |
| receptionist | See all appointments, confirm/reschedule/cancel, manage doctors, promote patients to doctor/receptionist, create bills, record payments, view reports |

New signups are patients. `project_description.md` says the first receptionist is set manually in Supabase.

### Frontend visibility vs backend authorization

- **Frontend:** sidebar items and per-route `role !== "..."` guards hide screens. This is **not** security.
- **Backend:** Supabase RLS policies on each table plus security-definer RPCs that check the caller's role via `auth.uid()`. The RLS policies for `profiles`, `doctors`, `appointments`, `prescriptions`, `bills` are **not in the repository** (they live in the Supabase project); their exact rules are **not confirmed from the current repository**. The only RLS confirmed in the repository is for `ai_conversations` / `ai_messages`.
- **AI Edge Function:** re-derives role from `profiles` using the caller's JWT and decides which tools exist.

**Rule for the gateway:** LiteLLM must **never** become the authority for CareBridge role permissions. It never sees, decides, or enforces roles.

---

## 10. Database Architecture

The base schema (tables, foreign keys, RLS, signup trigger) was created through Lovable/Supabase and is **not present as migrations in this repository**. The fields below are inferred from queries and inserts in `store.tsx`, `adapters.ts`, `index-gemini.ts`, and the four migrations.

### `profiles` (one row per auth user)

`id` (uuid, = `auth.users.id`), `full_name`, `email`, `role` (`patient`/`doctor`/`receptionist`), `phone`, `gender`, `date_of_birth`, `blood_type`, `allergies` (array or string), `conditions` (array or string), `address`, `emergency_contact_name`, `emergency_contact_relation`, `emergency_contact_phone`, `created_at` (per brief).

### `doctors`

`id` (uuid), `user_id` → `profiles.id` (FK named `doctors_user_id_fkey`, used in PostgREST joins), `specialization`, `consultation_fee` (numeric), `available_days` (text[] of `Mon`..`Sun`), `slots` (text[] like `"09:00 AM"`), `status` (`active`/`inactive`), `bio`, `room`. Doctor display name comes from the joined profile's `full_name`.

### `appointments`

`id`, `patient_id` → `profiles.id`, `doctor_id` → `doctors.id`, `appointment_date` (`YYYY-MM-DD`), `time_slot` (text, must match a doctor slot string), `reason`, `notes`, `status` (`requested`/`confirmed`/`completed`/`cancelled`), `created_at`.

### `prescriptions`

`id`, `appointment_id` → `appointments.id`, `doctor_id` → `doctors.id`, `patient_id` → `profiles.id`, `diagnosis`, `medicines` (JSON string of `{name, dosage, frequency, duration}[]`), `notes`, `created_at`. The frontend treats Postgres error `23505` on insert as "already has a prescription", implying a unique constraint on `appointment_id`; that constraint is **not confirmed from the current repository**.

### `bills`

`id`, `appointment_id` → `appointments.id`, `patient_id` → `profiles.id`, `amount` (numeric), `items` (JSON `{label, amount}[]`), `status` (`unpaid`/`paid`), `payment_method`, `paid_at`, `created_at`. Adapter also reads an optional `invoice_number`. `doctor_id` is not a bills column; the UI derives it from the appointment.

### `ai_conversations` / `ai_messages` (migration `20260922000000_add_ai_conversations.sql`)

- `ai_conversations`: `id`, `user_id` → `profiles.id`, `title`, `created_at`, `updated_at`.
- `ai_messages`: `id`, `conversation_id` → `ai_conversations.id` (on delete cascade), `user_id` → `profiles.id`, `role` (`user`/`assistant`), `content`, `created_at`.
- RLS enabled. Policies: SELECT/INSERT/UPDATE own conversations; SELECT/INSERT own messages in own conversations. **No DELETE policy** on either table.

### RPCs (migrations)

- `promote_patient_to_doctor(...)` — security definer, see Section 11.
- `promote_patient_to_receptionist(p_target_profile_id uuid)` — security definer, see Section 11.

### Index / constraint (migration)

- `appointments_active_slot_unique` — partial unique index, see Section 11.

---

## 11. Important Business Rules

All rules here must remain in CareBridge (Supabase database, RPCs, Edge Function). **None of them belong in LiteLLM.**

### Double booking

Migration `20260921000000_prevent_active_appointment_slot_conflicts.sql`:

```sql
create unique index if not exists appointments_active_slot_unique
on public.appointments (doctor_id, appointment_date, time_slot)
where status <> 'cancelled';
```

- Key: doctor + appointment date + time slot.
- Cancelled appointments do not occupy a slot. `requested`, `confirmed`, and `completed` appointments do.
- Enforced by the database, so concurrent inserts/updates fail with `23505`.
- Frontend: `/book` and the reschedule dialog hide taken slots using `isSlotTaken` (a client-side check over loaded appointments — a hint only). `bookAppointment` maps a `23505` on `appointments_active_slot_unique` to "This time slot was just booked by another patient".
- AI Edge Function: re-checks free slots before insert/update and maps `23505` to "That slot was just booked by someone else."

### Doctor promotion (patient → doctor)

Migration `20260921010000_promote_patient_to_doctor.sql`, called from `/doctors` via `supabase.rpc("promote_patient_to_doctor", ...)`.

- `security definer`, `search_path = public, pg_temp`, EXECUTE granted to `authenticated` only.
- Caller must be signed in and have `profiles.role = 'receptionist'`.
- Validates specialization (non-blank), fee > 0, ≥1 non-blank working day, ≥1 non-blank slot.
- Locks the target profile row (`for update`); target must currently be `patient` and must not already have a `doctors` row.
- In one transaction: sets `profiles.role = 'doctor'` and inserts the `doctors` row; returns the doctor row plus a `profile` object.
- There is no "create brand-new doctor account" flow; a doctor must first exist as a signed-up patient. `upsertDoctor` only edits existing doctors.

### Receptionist promotion (patient → receptionist)

Migration `20260923000000_promote_patient_to_receptionist.sql`. Same pattern: security definer, caller must be receptionist, target must be `patient`, row locked, sets `role = 'receptionist'`. Confirmed implemented and wired to `/doctors`.

### Appointment status changes

- Receptionist confirm: `status = 'confirmed'`.
- Cancel (patient or receptionist UI): `status = 'cancelled'`.
- Reschedule (`rescheduleAppointment`, receptionist UI): updates date/slot and sets `status = 'confirmed'`.
- Allowed transitions are not enforced in the frontend beyond button visibility. Database-level transition rules are **not confirmed from the current repository**.

### Prescription / consultation (doctor)

`completeConsultation` in `store.tsx`, used by `/consult/$id`:

1. Refuses if the appointment already has a prescription in loaded state.
2. Inserts `prescriptions` (appointment, doctor, patient, diagnosis, notes, `medicines` as JSON string).
3. Updates the appointment to `completed`.

These are two separate browser writes, not a transaction. If step 3 fails, a prescription exists for a non-completed appointment. `IMPLEMENTATION_PLAN.md` lists this as a known risk.

### Billing

- `/billing` lists `Completed` appointments with no existing bill.
- `createInvoice(appointmentId, items)` inserts `bills` with `amount` = sum of items **computed in the browser**, `items`, `status = 'unpaid'`.
- `markInvoicePaid(id, method)` sets `status = 'paid'`, `payment_method`, `paid_at = now()` (browser timestamp). The `/billing` UI only allows `cash`.
- One-bill-per-appointment is enforced only by UI filtering; a database constraint is **not confirmed from the current repository**.

---

## 12. Current AI Architecture

### Actual current flow (repository)

```text
Browser: CareBridgeAiPanel (/ai)
   │ 1. insert user message into ai_messages (RLS: own rows)
   │ 2. supabase.functions.invoke("carebridge-ai", { body: { message, messages: history } })
   │    (supabase-js attaches the user's JWT as Authorization: Bearer)
   ▼
Supabase Edge Function "carebridge-ai"   (source: supabase/functions/carebridge-ai/index-gemini.ts)
   │ - verify JWT, load role from profiles
   │ - build Gemini request (systemInstruction, contents, functionDeclarations)
   │ - loop ≤ 4 turns: call Gemini → execute requested tools → send functionResponse
   ▼
Google Gemini API (direct REST: generativelanguage.googleapis.com/v1beta/models/{model}:generateContent)
   model = "gemini-3.1-flash-lite"   (model-config-gemini.ts)
   ▲
   │ returns { text } to the browser
Browser: 3. insert assistant message into ai_messages, bump ai_conversations.updated_at
```

**The current implementation does not use OpenRouter.** An earlier version (`supabase/functions/carebridge-ai/index.ts` + `model-config.ts`, deleted in commit `bbef9cb` "Major UI overhaul") called `https://openrouter.ai/api/v1/chat/completions` with `OPENROUTER_API_KEY`, primary model `inclusionai/ling-3.0-flash-vl:free` and fallback `qwen/qwen3.8-27b:free`, and had doctor and receptionist tools. See Section 28.

### Frontend component

`src/components/clinic/carebridge-ai-panel.tsx`, rendered by `src/routes/_authenticated/ai.tsx`.

- Conversation list (create, select, rename, delete) from `ai_conversations`, ordered by `updated_at`.
- Messages from `ai_messages`, rendered with `react-markdown` for assistant replies.
- Role labels: Patient Assistant / Clinical Assistant / Front Desk Assistant.
- Patient quick prompts and quick actions (find doctor, slots, appointments, prescriptions, profile, book, cancel, reschedule).
- The browser persists both user and assistant messages; the Edge Function is stateless and never writes to `ai_*` tables.
- Sends the last **16** messages (including the new user message) as `messages`, plus `message`.
- Expects response `{ text: string }`; anything else is shown as a generic error.

### Edge Function request handling (`index-gemini.ts`)

- CORS: `Access-Control-Allow-Origin: *`, methods `POST, OPTIONS`.
- Requires `Authorization: Bearer <jwt>`; otherwise 401.
- Env vars (names only): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`. Missing → 500 "AI service is not configured."
- Creates a Supabase client with the **anon key** and forwards the user's JWT, so every query runs under the user's RLS.
- `auth.getUser(token)` must succeed; `profiles.role` must be one of the three roles, else 403.
- Body validation: `message` 1–4000 chars; `messages` optional array ≤ 16 items, each `{role: "user"|"assistant", content: 1–4000 chars}`; total history ≤ 24,000 chars.
- Converts history to Gemini format (`assistant` → `model`), appends the new message if not already last.
- Tools are attached only for `patient`. Non-patient system prompt: "General conversation is allowed, but no clinic data or actions are available for this role."
- Tool loop: up to 4 model calls. Each `functionCall` part is executed by `runTool(...)`, and a `functionResponse` part is appended. If the model returns text with no calls, reply `{ text }`.
- Errors: upstream 429 → 429 "temporarily rate-limited"; other upstream errors → 502; empty/invalid → 502; loop exhausted → 502; exception → 502. No retries, no fallback models (`fallbackModels: []`).
- The Gemini API key is sent as a `?key=` query parameter.

### Provider-specific coupling in the current function

- Hard-coded Gemini URL and REST shape.
- Gemini roles (`user`/`model`), `systemInstruction`, `functionDeclarations`, `functionCall`/`functionResponse` parts, `candidates[0].content.parts` parsing.
- Tool schemas are declared in OpenAI style and converted inline (`tools.map((tool) => tool.function)`).
- `GEMINI_API_KEY` is read inside the clinic Edge Function.

---

## 13. Current AI Capabilities

### Patient tools (all implemented in `runTool` in `index-gemini.ts`)

All queries run with the user's JWT, so RLS applies in addition to the explicit filters below. `patientId` is always the authenticated `auth.users.id`, never a model-supplied value.

| Tool | Inputs | Read/Write | What it actually does | Rules |
| --- | --- | --- | --- | --- |
| `get_doctors` | none | Read | Lists `doctors` with `status = 'active'`: id, name (joined profile `full_name`), specialization, fee, room | Active only |
| `get_available_slots` | `doctor_id`, `appointment_date` | Read | Loads doctor; if not active → "not available". If date's weekday is not in `available_days` → empty list. Otherwise returns doctor `slots` minus slots taken by non-cancelled appointments that day | UUID + real calendar date validated |
| `get_my_appointments` | none | Read | Caller's appointments (`patient_id = caller`) ordered by date, with doctor name/specialization/room/fee | Own rows only |
| `get_my_prescriptions` | none | Read | Caller's prescriptions (newest first): issued date, doctor, diagnosis, medicines, notes | Own rows only |
| `get_my_profile` | none | Read | Caller's profile: name, email, phone, gender, DOB, blood type, allergies, conditions, address, emergency contact | Own row only |
| `book_appointment` | `doctor_id`, `appointment_date`, `time_slot`, `reason` | **Write** (insert) | Inserts `appointments` row with `status = 'requested'`, `notes = ''` for the caller | Requires explicit confirmation + matching prior proposal + fresh availability check; DB unique index is final guard (Section 15) |
| `cancel_appointment` | `appointment_id` | **Write** (update) | Sets `status = 'cancelled'` | Appointment must belong to caller and be `requested` or `confirmed` |
| `reschedule_appointment` | `appointment_id`, `appointment_date`, `time_slot` | **Write** (update) | Moves to new date/slot with same doctor and sets `status = 'confirmed'` | Must belong to caller and be `requested`/`confirmed`; new slot must be free (excluding itself); `23505` handled. **No confirmation step**, and the result is auto-`confirmed` without receptionist review |

### Doctor tools

**None in the current function.** Doctors get general conversation only.

### Receptionist tools

**None in the current function.** Receptionists get general conversation only.

### Historic (deleted) tools — reference only

The deleted OpenRouter version (`git show e8ec4ec:supabase/functions/carebridge-ai/index.ts`) defined:

- Doctor: `get_today_schedule`, `get_patient_summary`, `get_patient_history`, `create_prescription`, `complete_consultation`.
- Receptionist: `search_patients`, `get_appointments`, `confirm_appointment`, `reschedule_appointment`, `cancel_appointment`, `promote_patient_to_doctor`, `create_invoice`, `mark_invoice_paid`.

These are **not** in the current codebase. They are useful only as a reference for V2 phases F and G.

---

## 14. Current AI Security Model

```text
Browser (user session JWT, publishable key only)
   ▼
Edge Function: require Bearer JWT → auth.getUser → profiles.role
   ▼
Tool allowlist by role (patient: 8 tools; doctor/receptionist: none)
   ▼
Input validation (UUID regex, real calendar date, string length limits, status checks)
   ▼
Supabase queries with anon key + caller JWT  (explicit patient_id = caller filters)
   ▼
RLS policies + constraints (unique slot index) as the final authority
```

What the model **does not** receive or control:

- No service-role key. The function only has the anon key and the caller's JWT.
- No SQL. The model can only name one of the declared tools; unknown names return "That action is not available."
- No identity choice. The patient id is taken from the verified JWT, never from tool arguments.
- No direct database access. All reads/writes are fixed queries inside `runTool`.
- Tool results are returned to the model as data; the model cannot widen them.

Where the security boundaries live today:

1. Supabase Auth (JWT validity).
2. Edge Function (role lookup, tool allowlist, argument validation, confirmation check).
3. PostgreSQL RLS and constraints (final authority).

The frontend is **not** a boundary. The provider (Gemini today, LiteLLM tomorrow) is **not** a boundary.

---

## 15. Existing AI Booking Protection

Current mechanism in `index-gemini.ts`:

1. **Proposal representation — textual marker.** The system prompt instructs the model to append, on its own line:
   `<carebridge-booking-proposal>{"doctor_id":"UUID","appointment_date":"YYYY-MM-DD","time_slot":"exact slot","reason":"exact reason"}</carebridge-booking-proposal>`
   The marker is part of the assistant text. The browser saves it in `ai_messages.content` and sends it back in `messages` history. The AI panel has no code that strips or specially renders the marker; how `react-markdown` displays it to the user is **not confirmed from the current repository**.
2. **Explicit confirmation detection.** `confirmed(lastMessage)` accepts only a whole message matching `yes | confirm | confirmed | please confirm | go ahead | book it | do it` (case-insensitive, optional trailing `!`/`.`/spaces).
3. **Proposal match.** `proposedBooking(history)` reads `history.at(-2)`, which must be an assistant message containing a valid marker (valid UUID, real date, slot ≤ 80 chars, non-empty reason). The `book_appointment` arguments must match the proposal exactly (doctor, date, slot, trimmed reason).
4. **Availability re-check.** `slots(...)` re-checks the doctor is active, works that weekday, and the slot is not taken by a non-cancelled appointment.
5. **Final database protection.** The insert can still fail on `appointments_active_slot_unique` (`23505`), which is reported as "That slot was just booked by someone else." RLS also applies to the insert.

Weaknesses (why V2 replaces it): the proposal depends on the model emitting an exact text marker; the marker is mixed into the stored chat text; confirmation is regex-based; and the proposal is reconstructed from client-supplied history, which the browser controls.

V2 will replace this with a **structured application-level proposal** (Section 23). Not redesigned here.

---

## 16. Why AI V2 Exists

The current AI function mixes, in one ~600-line file:

- agent logic (system prompt, turn loop),
- provider choice (Gemini),
- model selection (`gemini-3.1-flash-lite`),
- provider API handling (URL, auth query param, request/response shapes, role names, function-call format),
- fallback behaviour (none; previously hand-coded for OpenRouter),
- tool orchestration (declarations, dispatch, result formatting),
- conversation handling (history validation and conversion).

Consequences:

- Changing provider or model means rewriting request building, response parsing, tool-call format, and error handling inside the security-critical clinic function. This already happened once (OpenRouter → Gemini), and the doctor/receptionist tools were lost in that rewrite.
- No retries, no fallbacks, no central timeouts. A single free-tier rate limit (429) takes the assistant down.
- Provider keys live next to clinic authorization code.
- Model/provider changes require a redeploy of the clinic Edge Function.

V2 separates **model infrastructure** (LiteLLM) from **application logic and security** (Edge Function + Supabase).

---

## 17. AI V2 Target Architecture

```text
CareBridge Frontend (Vercel: carebridge-clinic-flow)
        │  supabase.functions.invoke(...)  with user JWT
        ▼
Supabase Edge Function (AI V2)
        │  OpenAI-compatible chat/completions request, model = "carebridge-agent"
        │  authenticated to the gateway with a gateway key (server-to-server)
        ▼
LiteLLM Gateway (Vercel: CareBridge AI Gateway)
        │  routing, retries, timeouts, fallbacks
        ▼
Primary / Fallback / Additional models (Gemini first)
```

### Frontend — responsible for

- chat UI and conversation list,
- persisting and displaying messages,
- collecting explicit user confirmation (V2: a confirm action on a structured proposal),
- rendering structured application responses (for example a booking proposal card).

### Supabase Edge Function — responsible for

- authentication (verify the user JWT),
- identity and role (from `profiles`),
- authorization and role-specific tool allowlists,
- tool registry, tool argument validation, tool execution,
- business rules and database operations (under the caller's RLS),
- confirmation and security checks,
- calling LiteLLM with a provider-neutral request and the `carebridge-agent` alias.

### LiteLLM — responsible for

- model/provider abstraction (one OpenAI-compatible API),
- model routing via the `carebridge-agent` alias,
- primary model selection,
- fallbacks,
- retries,
- timeouts,
- provider-level failure handling (rate limits, 5xx),
- centralized model configuration and provider API keys.

### Supabase — responsible for

- PostgreSQL data,
- RLS,
- constraints (for example `appointments_active_slot_unique`),
- RPCs (for example promotions),
- persistent state (including `ai_conversations` / `ai_messages`),
- final source of truth.

---

## 18. What LiteLLM Must NOT Do

LiteLLM must **NOT**:

- authenticate CareBridge users,
- determine whether a patient can see another patient's data,
- decide whether a doctor (or anyone) may perform an action,
- access Supabase directly (no Supabase URL, no Supabase client),
- receive service-role credentials (or any Supabase key),
- execute arbitrary SQL,
- execute CareBridge tools,
- contain CareBridge business rules (booking, slots, promotions, billing, prescriptions),
- replace RLS,
- replace the Supabase Edge Function,
- become the clinic backend,
- be called directly by the browser in the final architecture.

The intended flow:

```text
Frontend → Edge Function → LiteLLM → Edge Function → Supabase
```

NOT:

```text
Frontend → LiteLLM → Supabase
```

LiteLLM only receives messages and tool **schemas** from the Edge Function and returns model output (text and/or tool-call requests). The Edge Function decides whether to execute any tool call.

---

## 19. V2 Deployment Architecture

| Project | Hosting | Contents |
| --- | --- | --- |
| `carebridge-clinic-flow` (existing) | Vercel project `carebridge-clinic-flow` | Frontend; Supabase migrations and Edge Function source |
| `carebridge-liteLLM` (new) | New Vercel project "CareBridge AI Gateway" | LiteLLM gateway configuration only |

Local layout:

```text
InternAssignmentShahriar/
├── carebridge-clinic-flow/
└── carebridge-liteLLM/
```

They are intentionally separate: separate repositories, deployments, secrets, and release cycles. The clinic project must not depend on gateway source code, only on a gateway URL and gateway key configured as Supabase Edge Function secrets. Whether LiteLLM runs well on Vercel (Python runtime, cold starts, request duration limits) is **not confirmed** and should be validated in Phase A.

---

## 20. Initial LiteLLM Goal

The first milestone is intentionally tiny:

```text
LiteLLM → Gemini
```

- Expose one model alias: **`carebridge-agent`**.
- Map it to Gemini model **`gemini-3.1-flash-lite`** (the model currently used by the CareBridge Edge Function).
- Serve the OpenAI-compatible chat completions API.
- Support tool/function calling pass-through (the Edge Function will send tool schemas).

The CareBridge application should eventually call only `carebridge-agent`, never a provider-specific model name. Provider/model details stay hidden in the gateway.

---

## 21. Gemini Integration

The developer already has a Gemini API key obtained from Google AI Studio.

Environment variable name: **`GEMINI_API_KEY`**

- It belongs on the **LiteLLM server side** (gateway environment variables).
- It must **never** reach the browser.
- It must **not** be committed (use Vercel environment variables / local untracked env files).
- It will initially be used for the Gemini provider behind `carebridge-agent`.

Note: the current CareBridge Edge Function also reads a secret named `GEMINI_API_KEY`. In V2 that secret moves out of the clinic function; the Edge Function will instead hold a gateway URL and gateway key (the AI V2 audit proposes the names `LITELLM_GATEWAY_URL` and `LITELLM_API_KEY`; final names are not yet decided in code).

---

## 22. Future Model/Fallback Strategy

```text
carebridge-agent
    ↓
Primary
    ↓
Fallback 1
    ↓
Fallback 2
```

- First milestone: **Gemini only**, no fallbacks.
- Later, adding or changing a model should require only:
  - model name,
  - provider/model identifier,
  - the corresponding provider API key environment variable,
  - LiteLLM routing configuration.
- None of these changes should touch the CareBridge frontend, and ideally not the Edge Function either (it keeps calling `carebridge-agent`).
- Every model placed behind `carebridge-agent` must support tool/function calling, because the Edge Function depends on it.

---

## 23. V2 Structured Booking

Intended future flow:

```text
AI
 ↓  returns a structured booking proposal (not a text marker)
Structured booking proposal  (e.g. { doctor_id, appointment_date, time_slot, reason })
 ↓
Frontend confirmation  (explicit Confirm button bound to that proposal)
 ↓
Edge Function validation  (identity, role, argument validation)
 ↓
Availability recheck
 ↓
Database insert  (RLS + appointments_active_slot_unique as final guard)
```

Why this is better than textual markers:

- The proposal is data produced and checked by the application, not a string the model must format exactly.
- Confirmation is an explicit UI action tied to one proposal, not a regex over free text.
- The booking write can be triggered without going through the model at all.
- It removes provider-dependent formatting behaviour from a security-relevant path.

This is application logic. It lives in the Edge Function and frontend, **not** in LiteLLM. Not implemented yet.

---

## 24. V2 Development Roadmap

| Phase | Name | Intent |
| --- | --- | --- |
| A | LiteLLM infrastructure | Create `carebridge-liteLLM`, configure `carebridge-agent` → Gemini, deploy to the new Vercel project, secure it with a gateway key, test with an OpenAI-compatible client (plain chat + one tool-call round-trip). |
| B | Minimal Edge Function | New V2 Edge Function that authenticates the user, loads the role, calls LiteLLM (`carebridge-agent`), and returns `{ text }`. No tools. Frontend contract unchanged. |
| C | Tool framework | Provider-neutral tool registry in the Edge Function: role-based allowlists, argument validation, dispatch, OpenAI-format tool-call loop through LiteLLM. |
| D | Patient tools | Re-implement the eight current patient tools (Section 13) on the new framework. |
| E | Structured booking | Replace the text-marker proposal with a structured proposal + frontend confirmation (Section 23). |
| F | Doctor tools | Add doctor tools (reference: deleted OpenRouter version), respecting RLS and consultation rules. |
| G | Receptionist tools | Add receptionist tools (confirm/reschedule/cancel, promotions via RPC, billing), respecting RLS and RPC checks. |
| H | Production / security testing | Role isolation, cross-patient access attempts, prompt-injection attempts, tool-argument fuzzing, rate limits and fallback behaviour, gateway outage behaviour, timeouts. |

---

## 25. Current Status

### COMPLETED (confirmed in repository)

- Supabase email/password auth, Google OAuth call, session restoration, profile/role lookup.
- Role-specific sidebars, dashboards, and route guards.
- Supabase-backed `ClinicProvider` with adapters (no mock fallback).
- Booking, confirm, cancel, reschedule, consultation + prescription, billing + payment.
- Patient profile editing.
- Database double-booking protection (`appointments_active_slot_unique`).
- Patient → doctor and patient → receptionist promotion RPCs.
- AI conversation persistence (`ai_conversations`, `ai_messages`, RLS).
- AI chat UI.

Runtime verification of each workflow against the live project is **not confirmed from the current repository** (no automated tests).

### IN PROGRESS

- AI V2 planning (audit documents in `opinions/`).
- LiteLLM gateway project creation (outside this repository).

### PLANNED

- LiteLLM gateway (Phase A) and V2 Edge Function (Phases B–H).
- Structured booking proposals.
- Doctor and receptionist AI tools (again).
- Assessment 2 items: automations (reminders, waitlist), RAG on ≥5,000 records, classification accuracy ≥70%, automated tests. None of these exist in the repository yet.

### DEPRECATED / TO BE REPLACED

- `supabase/functions/carebridge-ai/index-gemini.ts` — old/reference AI implementation (direct Gemini, patient tools only).
- `supabase/functions/carebridge-ai/model-config-gemini.ts`.
- The `<carebridge-booking-proposal>` text-marker booking flow.
- `GEMINI_API_KEY` as an Edge Function secret (moves to the gateway).

**LiteLLM is not yet integrated** with CareBridge in any way.

---

## 26. Things the Gateway Developer Must Preserve

1. Do not modify the `carebridge-clinic-flow` project from the gateway work.
2. LiteLLM never accesses Supabase and never holds Supabase keys.
3. No provider secrets in any frontend or in the clinic repository.
4. No provider-specific model names in the CareBridge frontend; the app targets `carebridge-agent`.
5. The Supabase Edge Function remains the security boundary (auth, role, tools, validation).
6. Supabase remains the source of truth (data, RLS, constraints, RPCs).
7. LiteLLM remains model infrastructure only (routing, fallbacks, retries, timeouts, provider keys).
8. The gateway must require its own key; it must not be an open proxy.
9. The browser does not call LiteLLM directly.
10. First milestone is Gemini-only (`carebridge-agent` → `gemini-3.1-flash-lite`).
11. Future model additions are configuration-driven.
12. Every model behind `carebridge-agent` must support tool calling.
13. Never commit `.env` files or keys.

---

## 27. Useful File/Code References

All paths are relative to `carebridge-clinic-flow/` and exist in the current repository.

| Area | File |
| --- | --- |
| AI Edge Function (current) | `supabase/functions/carebridge-ai/index-gemini.ts` |
| AI model config (current) | `supabase/functions/carebridge-ai/model-config-gemini.ts` |
| AI chat UI | `src/components/clinic/carebridge-ai-panel.tsx` |
| AI route | `src/routes/_authenticated/ai.tsx` |
| Clinic store | `src/lib/clinic/store.tsx` |
| Clinic types | `src/lib/clinic/types.ts` |
| Clinic adapters | `src/lib/clinic/adapters.ts` |
| Helpers / historic seed data | `src/lib/clinic/data.ts` |
| Supabase client | `src/lib/supabase/client.ts` |
| Auth/session | `src/lib/auth/store.ts` |
| Global auth redirect | `src/routes/__root.tsx` |
| Authenticated layout | `src/routes/_authenticated.tsx` |
| Role navigation | `src/components/clinic/app-shell.tsx` |
| Booking screen | `src/routes/_authenticated/book.tsx` |
| Appointments screen | `src/routes/_authenticated/appointments.tsx` |
| Consultation screen | `src/routes/_authenticated/consult.$id.tsx` |
| Doctor management / promotions | `src/routes/_authenticated/doctors.tsx` |
| Billing | `src/routes/_authenticated/billing.tsx` |
| Double-booking migration | `supabase/migrations/20260921000000_prevent_active_appointment_slot_conflicts.sql` |
| Doctor promotion RPC | `supabase/migrations/20260921010000_promote_patient_to_doctor.sql` |
| AI conversations migration | `supabase/migrations/20260922000000_add_ai_conversations.sql` |
| Receptionist promotion RPC | `supabase/migrations/20260923000000_promote_patient_to_receptionist.sql` |
| AI V2 audit (background) | `opinions/AI_V2_AUDIT.md`, `opinions/AI_V2_CLEANUP_REPORT.md`, `opinions/V2_MIGRATION_CHECKLIST.md` |
| Assignment briefs | `project_description.md`, `project_description_update.md` |
| Historic OpenRouter function (git only) | `git show e8ec4ec:supabase/functions/carebridge-ai/index.ts` |

---

## 28. Known Documentation / Implementation Discrepancies

Recorded as found. Not fixed.

1. **`kt.md` is empty.** The file exists but is 0 bytes (added empty in commit `bbef9cb`). `opinions/AI_V2_AUDIT.md` and `opinions/AI_V2_CLEANUP_REPORT.md` cite "KT sections 1–35", "KT section 21", and "KT section 27"; that content cannot be verified from the repository.
2. **OpenRouter vs Gemini.** The expected architecture "Frontend → Edge Function → OpenRouter → model" is no longer true. The repository currently calls the Gemini REST API directly. OpenRouter was used by the deleted `index.ts` / `model-config.ts` (removed in `bbef9cb`).
3. **Doctor/receptionist AI tools.** Commit `367a709` added doctor and receptionist tools. The current `index-gemini.ts` has patient tools only; doctors and receptionists get tool-less general chat. The UI still labels them "Clinical Assistant" / "Front Desk Assistant".
4. **Edge Function entry file.** The function directory contains `index-gemini.ts` but no `index.ts`, and there is no `supabase/config.toml` setting a custom entrypoint. The Supabase CLI defaults to `index.ts`. Which code is actually deployed as `carebridge-ai` in the live project is **not confirmed from the current repository**.
5. **`IMPLEMENTATION_PLAN.md` is stale (dated 2026-09-18).** It lists Google OAuth as deferred (now implemented in code), patient profile editing as not started (implemented), slot-conflict guards as not started (the unique index migration exists), and refers to `BACKEND_GUIDE.md`, which does not exist in the repository.
6. **`README.md` is stale.** It describes a mock-data prototype with a role switcher. The app is Supabase-backed and the role comes from `profiles.role`; there is no role switcher. `DEMO_USERS` only prefill the login email.
7. **Frontend Supabase key variable name.** `project_description.md` and the AI audit documents use `VITE_SUPABASE_ANON_KEY`. The code (`src/lib/supabase/client.ts`) and local env file use `VITE_SUPABASE_PUBLISHABLE_KEY`.
8. **AI conversation delete vs RLS.** The AI panel calls `delete()` on `ai_conversations`, but the migration defines no DELETE policy on `ai_conversations` or `ai_messages`. Under RLS a delete with no permitted rows returns no error, so the UI may report "Conversation deleted" while the row persists. Runtime behaviour is **not confirmed**.
9. **AI audit line numbers/sizes.** `opinions/AI_V2_AUDIT.md` describes `index-gemini.ts` as 640 lines and cites specific line ranges; the current file is about 614 lines, so those references are approximate.
10. **"Frontend stays exactly as-is" in V2.** `opinions/AI_V2_AUDIT.md` says the frontend will not change in V2. The planned structured booking (Section 23) requires a frontend confirmation UI, so at least that part of the frontend will change.
11. **Model name in the Assessment 2 brief.** `project_description_update.md` suggests `gemini-1.5-flash`; the repository uses `gemini-3.1-flash-lite`.
12. **Base schema not in migrations.** Assignment docs describe `profiles`, `doctors`, `appointments`, `prescriptions`, `bills` and RLS, and `IMPLEMENTATION_PLAN.md` mentions a signup trigger. None of these are in `supabase/migrations/`; only the four incremental migrations are.
13. **Reschedule auto-confirms.** Both the receptionist reschedule (`rescheduleAppointment`) and the AI patient tool `reschedule_appointment` set `status = 'confirmed'`. For patient-initiated AI reschedules this bypasses receptionist confirmation, unlike a new booking (`requested`). This is current behaviour, not necessarily the intended rule.

---

## 29. Final Architecture Diagram

```text
                    ┌──────────────────────────────────────┐
                    │        CareBridge Frontend           │
                    │  Vercel: carebridge-clinic-flow      │
                    │  chat UI · confirmations · rendering │
                    └──────────────────┬───────────────────┘
                                       │ user JWT (supabase.functions.invoke)
                                       ▼
┌──────────────────────┐   ┌──────────────────────────────────────┐
│      Supabase        │◄──┤      Supabase Edge Function          │
│  PostgreSQL · RLS    │   │  auth · role · tool allowlist        │
│  constraints · RPCs  │──►│  validation · tool execution         │
│  ai_conversations    │   │  business rules · confirmation       │
│  source of truth     │   └──────────────────┬───────────────────┘
└──────────────────────┘                      │ OpenAI-compatible request
         ▲                                    │ model = "carebridge-agent"
         │  (queries run under caller's RLS)  │ + gateway key
         │                                    ▼
         │                 ┌──────────────────────────────────────┐
         │                 │           LiteLLM Gateway            │
         │   NO ACCESS ✗   │  Vercel: CareBridge AI Gateway       │
         └─────────────────┤  routing · retries · timeouts        │
                           │  fallbacks · provider keys           │
                           └──────────────────┬───────────────────┘
                                              │
                                              ▼
                           ┌──────────────────────────────────────┐
                           │   Primary / Fallback Models          │
                           │   Milestone 1: Gemini                │
                           │   (gemini-3.1-flash-lite)            │
                           └──────────────────────────────────────┘
```

Flow for one assistant turn:

```text
Frontend → Edge Function → LiteLLM → model
                ▲              │
                └──────────────┘  (text or tool-call request)
Edge Function executes allowed tools → Supabase (RLS) → results → LiteLLM → final text → Frontend
```
