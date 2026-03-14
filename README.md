# FlashVote - Secure Digital Election Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/goodyness/electronic_election_platform)
[![Django](https://img.shields.io/badge/Django-4.x-092e20?logo=django)](https://www.djangoproject.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.x-38bdf8?logo=tailwind-css)](https://tailwindcss.com/)

FlashVote is a robust, enterprise-grade digital voting system designed to facilitate secure and transparent elections for institutions and organizations.

> [!IMPORTANT]
> **Production Use Disclaimer**: This source code is provided for **educational purposes and development testing only**. Commercial or production use is strictly prohibited without explicit authorization. You are welcome to fork or clone this repository for learning and research.

---

## 🚀 Key Features

### 🛡️ Security & Integrity (Trust by Design)
- **Deterministic Result Hashing**: Implements SHA-256 hashing of the result ledger to ensure vote immutability. Once an election is sealed, the results are cryptographically verifiable.
- **Vote Signatures**: Every vote cast is signed with an HMAC-SHA256 signature, linking the vote data to a secure verification ID.
- **Immutable Audit Trail**: Comprehensive logging of administrative actions, status changes, and authentication events with IP and device tracking.
- **Secure Authentication**: Multi-factor authentication support via Email OTP and robust role-based access control (RBAC).

### 💳 Monetization & Scalability
- **Paystack Integration**: Seamless automated payment workflows for multi-tiered election plans (Free, Basic, Standard, Premium).
- **Multi-Tenancy Architecture**: Supports multiple institutions simultaneously, each with independent election management and custom branding.
- **Flexible Election Plans**: Plan-based restrictions on voter capacity and branding features like custom logos and themes.

### 📊 Advanced Analytics & Reporting
- **Real-time Turnout Analytics**: Track voter participation rates as they happen with faculty and department-level granularity.
- **Public Audit Portal**: Enables transparent verification of election integrity without compromising voter anonymity.
- **Sentiment Surveys**: Built-in feedback system for voters to provide ratings and reviews on the election process.
- **PDF Export**: Generate professional election reports and analytics summaries.

---

## 🛠️ Tech Stack

- **Backend**: [Django 4.2+](https://www.djangoproject.com/) (Python)
- **Database**: [PostgreSQL](https://www.postgresql.org/) (Recommended for production integrity)
- **Frontend**: [Tailwind CSS](https://tailwindcss.com/), [Alpine.js](https://alpinejs.dev/)
- **Payments**: [Paystack API](https://paystack.com/)
- **Caching/Task Queue**: [Redis](https://redis.io/) & [Celery](https://docs.celeryq.dev/) (Optional but recommended for large-scale mailings)

---

## 📂 Project Structure

```bash
election/
├── election_core/          # Core Business Logic & Models
│   ├── voting_logic.py     # Deterministic tallying and hashing
│   ├── payment_views.py    # Paystack gateway integration
│   ├── admin_views.py      # Institution management
│   ├── analytics_pdf_utils # PDF generation logic
│   ├── tasks.py            # Async email & background tasks
│   └── models.py           # Integrity-focused data schema
├── election_admin/         # custom administrative extensions
├── templates/              # Modern, responsive UI templates
├── static/                 # Tailwind builds and interactive assets
├── manage.py               
└── requirements.txt        
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Node.js & npm (for Tailwind builds)

### Quick Start

1. **Clone & Setup Environment**
   ```bash
   git clone https://github.com/goodyness/electronic_election_platform.git
   cd election
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   Create a `.env` file in the root directory (refer to `settings.py` for required variables like `SECRET_KEY`, `PAYSTACK_SECRET_KEY`, etc.)

3. **Initialize Database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

---

## 🤝 Contributing & Forking

This project is open for educational contributions. Feel free to:
- **Fork** the repository to experiment with voting algorithms.
- **Submit PRs** for bug fixes or UI enhancements.
- **Report Issues** if you find security vulnerabilities or bugs.

---

## 📄 License

This repository is licensed under the MIT License. However, please respect the **Production Use Disclaimer** regarding non-educational deployments.

---

**Built with ❤️ for secure and transparent digital democracy.**
etails.

## 📞 Support

For issues or questions, please open an issue on the GitHub repository.

---

**Built with ❤️ for secure and transparent elections**