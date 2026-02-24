# General User Guide: How to Use the Election Platform

This document provides step-by-step instructions for all user roles interacting with the Electronic Election Platform.

---

## 1. Guide for Grand Admin (System Administrator)

The Grand Admin role manages the entire ecosystem, handling approvals, system settings, and global analytics.

### Approving Election Organizers
1. Navigate to the **Grand Admin Dashboard**.
2. Click on **Manage Organizers** or view **Pending Approvals**.
3. Review the organizer's details (Institution, Name).
4. Click **Approve** to grant them access to create elections, or **Reject** if invalid.

### Managing Institutions
1. Go to the **Institutions** panel.
2. Add new institutions that are recognized by the platform to allow organizers to associate with them.

### Monitoring & Analytics
1. View overall platform health, total revenue, active elections, and user counts via the **System Analytics** tab.
2. Monitor the **Audit Logs** to track administrative actions, ensuring no unauthorized changes are made.
3. Track **Payments** to resolve any Paystack transaction disputes.

### System Configuration
1. Use the toggle buttons on the dashboard to globally enable/disable OTP verification emails or Voting receipts if server loads get too high.
2. Manage **Plan Pricing** to adjust the cost per email limit for Free, Basic, Standard, and Premium tiers.

---

## 2. Guide for Election Organizers

As an Election Organizer, you are responsible for setting up and running a seamless election.

### Registration & Approval
1. Go to the **Organizer Signup** page.
2. Fill out your details and select your Institution.
3. Wait for a **Grand Admin** to review and approve your account. You will not be able to create elections until approved.

### Creating an Election
1. Once approved, log into the **Organizer Dashboard**.
2. Click **Create Election**. Provide the title, start/end dates, and other basic info.
3. **Select a Plan:** Choose between Free, Basic, Standard, or Premium based on your expected voter turnout (Allowed Emails list size). 
4. If choosing a paid plan, proceed to the checkout and complete payment via Paystack.

### Setting Up the Ballot
1. Open your Election Management panel.
2. **Add Positions:** Create positions (e.g., President, Secretary, SUG Rep, etc.).
3. **Add Candidates:** Under each position, add candidates. You can include their names, popular aliases (AKA), biographies, and upload their photos.

### Adding Allowed Voters
1. Go to **Voter List Management** for your election.
2. Provide the email addresses of all individuals authorized to vote. **Only** these email addresses will be able to receive OTPs and cast a ballot.

### Monitoring the Election
1. Once the election start time hits, its status changes to **Active**.
2. Visit the **War Room** to view real-time incoming votes and turnout percentages.
3. You can manually **Freeze** the election if there is a suspected issue, or send **Nudges (Reminders)** to allowed voters who haven't voted yet.

### Post-Election
1. Once the end time is reached, the election automatically closes.
2. Navigate to the results tab to view the final outcomes.
3. Click **Export CSV** or **Export PDF** to generate official signed result sheets.

---

## 3. Guide for Voters

Voting is designed to be fully secure and straightforward.

### Accreditation & Login
1. When an election starts, visit the specific voting link/gateway provided by your Election Organizer.
2. Enter your authorized email address.
3. If your email is on the **Allowed List**, the system will send a One-Time Password (OTP) to your inbox.
4. Enter the 6-digit OTP to verify your identity. (OTP expires after a short period, so use it quickly).
5. Complete any extra profile requirements (like Matric Number, Faculty, Department) if prompted.

### Casting Your Vote
1. Upon successful accreditation, you will be redirected to the **Ballot Page**.
2. Review the positions and the candidates running for them.
3. Select your preferred candidate for each position.
4. Submit your vote. **Note:** Once submitted, votes are cryptographically locked and **cannot be changed**.

### Verifying Your Vote
1. After voting, you will be presented with a **Verification ID** (and an email receipt if enabled by the overall platform and the specific election).
2. You can use this Verification ID on the platform's **Verify Ballot** page to independently confirm that your vote was recorded securely in the database and has not been tampered with.
