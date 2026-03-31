# Electronic Election Platform - Project Documentation

## Project Overview
The Electronic Election Platform is a secure, robust, and scalable web-based voting system built meticulously with Django Python. It is designed to handle multiple institutional and organizational elections ranging from small departments to university-wide faculties. The system emphasizes tight security schemas, voter transparency, real-time analytics, and tremendous ease of use, ensuring an uncompromised one-person-one-vote policy.

## Architecture & Tech Stack
- **Backend Framework:** Django (Python)
- **Database:** PostgreSQL (Optimized for robust row-level security and high transaction rates)
- **Authentication:** Custom OTP-based email verification OR Batched UUID Token Verification, Role-based Access Control (RBAC)
- **Payment Gateway:** Paystack Integration for plan purchases via API integration.
- **Security:** HMAC-SHA256 signature for vote tampering prevention, comprehensive Audit Logging.
- **Frontend Engine:** Django Templates augmented with modern CSS libraries (Tailwind/Bootstrap/Alpine) and highly-performant **HTMX** for smooth, asynchronous fragment updates without full-page reloads.

## Core Features & Modules

### 1. Multi-Tiered User Roles
- **Grand Admin:** The superuser who oversees the entire platform, manages institutions, approves Election Organizers, monitors system-wide analytics, handles overall payment gateways, and dynamically manages subscription plan pricing limits.
- **Election Organizer:** Users who create and manage elections. They must be explicitly approved by the Grand Admin before fully utilizing the platform to prevent fraudulent setups.
- **Voter:** End-users dynamically participating in active elections using strictly monitored workflows.

### 2. Election Management Architecture
- **Drafting & Activation:** Organizers can heavily configure elections, detailing open/close times, and allowing the daemon/time-check processes to freeze, start, or conclude them.
- **Positions & Candidates Registry:** Support for creating multiple nested positions per election with detailed candidate profiles (Photos, bios, faculties, departments, and popular AKA names).
- **Voter Allowed-List Integration:** Organizers can define a roster of strictly allowed emails. Only these email endpoints can authenticate against the election DB, thwarting unauthorized external intrusion.

### 3. Subscription & Tiered Payment System
Elections are algorithmically grouped under four major pricing limits managed by the Grand Admin:
- **Free Plan:** Small scale (Strict cutoff on allowed-email limits, typically 50).
- **Basic Plan:** Medium scale (Up to 1,000 emails max).
- **Standard Plan:** Large scale (Up to 5,000 emails max).
- **Premium Plan:** Enterprise scale (Unlimited emails, custom URL slugs for isolated routing, custom visual themes).
All commercial plans utilize Paystack's API Webhooks to verify transitions automatically without manual backend intervention.

### 4. Advanced Security & Zero-Tamper Integrity
- **Ballot Signatures:** Every vote cast is cryptographically signed at runtime using HMAC-SHA256, protecting against underlying database tampering. Attempting to manually spoof values in the DB raises immediate signature mismatches.
- **Verification ID Receipts:** Voters securely receive mathematically unique receipt IDs to verify their row states independently.
- **Anti-Fraud System:** Strict view-level validation preventing double-voting race conditions, utilizing generic IP & User Agent DB schemas, and time-bound OTP expiration lifecycles.
- **Global Audit Logs:** Middleware and action-triggered tracking over user actions (especially by Organizers and Grand Admins) ensuring strong system forensics and accountability.

### 5. Analytics & Live Operational Results
- **Visual War Room Dashboard:** Real-time computational analytics, metric charts, and numerical statistics aggressively tracking live voter turnout, total remaining unaccredited voters, and current leading candidates per post.
- **Verifiable Data Export:** Post-election or post-audit rules allow organizers and system admins to safely export final results and audit records securely into standard CSV and encrypted PDF forms.

## System Workflow Pipeline
1. **Onboarding:** Organizer registers specifying details -> Grand Admin forensically Reviews and Approves.
2. **Setup Phase:** Organizer initiates an Election instance -> System forces them to Select & Pay for an applicable Plan depending on their scale target -> Organizers input Candidates per Position -> Organizers populate the strict Allowed Emails payload.
3. **Execution Phase:** Election time hits DB trigger boundaries (Status=Active) -> Voters arrive at gateway and authenticate via backend-SMTP OTP routing -> Submit Validated Votes -> Acquire Digital Verification Receipts -> Election tallies iterate dynamically.
4. **Conclusion:** End time triggers database boundary (Status=Closed) -> Operations halt -> System officially locks tallies -> Organizer exports official PDF/CSV certificates.
