# FoodShare Tracker - FIT1056 Team 30 (Deliverable 2)

## Overview:

FoodShare Tracker helps the Community Harvest Food Bank manage donations, stock, client households, food allocation and pickups in one place. It is a Streamlit app that runs locally on the food bank's computer and stores everything in JSON files, so it works without an Internet connection.

The system is built around a human-centred approach: it only collects the client information it needs, keeps dietary and accessibility needs only with consent, never lets an allergy or religious need be overridden, and shows volunteers only what they need to pack an order.

## Project Structure:

app/ - classes and business logic
- user.py - User (Administrator, Staff, Volunteer)
- donation.py - Donor, DonationBatch
- household.py - Household, ConsentRecord
- order.py - Order, Substitution
- task.py - Task (volunteer jobs)
- records.py - AuditLogEntry, NotificationRecord
- manager.py - FoodShareManager: loads/saves the data and holds all the rules
- admin_utils.py - logging and data backups

gui/ - Streamlit pages
- main_dashboard.py - sign in, 10 minute timeout, menu for each role
- home_page.py, donation_pages.py, inventory_pages.py, household_pages.py, order_pages.py, volunteer_pages.py, report_pages.py, admin_pages.py

config/ - settings kept outside the code (NFR-14)
- dietary_config.json - dietary attributes, dietary rules, reason codes, pickup slots, contact methods
- messages.json - notification message templates

data/foodshare.json - the data file (demo data included)

tests/ - pytest unit tests

main.py - starts the app, seed_data.py - resets the demo data

## Installation / Setup:

Requirements: Python 3.x

1. Clone the repository:
   git clone https://github.com/Munity2325/FIT1056-group-project-application.git
   cd FIT1056-group-project-application
2. (Optional) create and activate a virtual environment:
   python -m venv .venv
   .venv\Scripts\activate (Windows) or source .venv/bin/activate (Mac/Linux)
3. Install the packages:
   pip install -r requirements.txt

## How to Run:

From the project folder run:

streamlit run main.py

Demo accounts:
- grace / admin123 - Administrator
- kristine / staff123 - Staff
- weisheng / volunteer123 - Volunteer

To reset the demo data run: python seed_data.py

To run the tests: python -m pytest

## Features:

Accounts and access (F-01)
- Sign in with username and password, passwords stored as salted hashes
- Signed out automatically after 10 minutes without activity
- Each role only sees its own pages, admins can create, disable and re-enable accounts and change roles

Donations (F-02)
- Record a donation with one or more batches, dietary attributes picked from a fixed list
- Anonymous donations, or donor details with contact consent
- Expired items are refused and can be recorded as a disposal
- Donation confirmation with a reference (DON-0001)

Inventory (F-03)
- Stock list with quantity, expiry, storage and shelf, earliest expiry first
- Dashboard shows stock expiring in the next 7 days
- Staff and volunteers record damaged or missing stock with a reason code, saved to the audit log

Client households (F-04)
- Only the needed details, each field explains why it is asked, no income or ID fields
- Dietary and accessibility needs only saved with consent, withdrawing consent deletes them
- Private staff notes that volunteers never see

Food allocation and pickup (F-05)
- Suggested allocation from household size, needs and stock
- Allergy, medical and religious needs can never be overridden, preferences only with a written reason
- Pickup time from the household's preferred times, optional alternative collector
- Order statuses: Requested, Approved, Packed, Ready, Collected, Not Collected
- Substitutions that still suit the household

Volunteer tasks (F-06)
- Approved orders become packing tasks, volunteers claim, start and complete them (user and time recorded)
- Picking list shows order reference, bag, items, quantities, shelf and packing notes only
- Completing a packing task takes the items out of stock

Reports (F-07)
- Demand report (requested, supplied, unavailable and substitutes) and fairness report (by household size and staff member)
- No client names or contacts, export to CSV

Notifications (F-08)
- Pickup confirmations and substitution messages are simulated and written to the notification log with the client's contact method
- Messages only contain the order reference and pickup time

Admin
- Logging to foodshare.log and a backup of the data file at the start of each session

## Testing:

python -m pytest runs 68 tests:
- 50 unit tests (positive, negative and boundary cases) for accounts, donations, inventory, households, orders, tasks and reports
- 8 MC/DC tests for the login decision and the order item decision (tests/test_mcdc.py)
- 10 functional end-to-end tests that click through the real Streamlit app as each role (tests/test_functional.py)

Each test uses its own temporary data file, so the demo data is not changed.

## Changes from Deliverable 1 / Known Limitations:

- Streamlit and JSON files are used instead of Tkinter and SQLite (see Section 4.5 of the report)
- Data files are not encrypted (NFR-05), protection relies on the computer's login
- Notifications are simulated in a log instead of sending real SMS or email
- Clients do not sign in themselves, staff enter their details with them, so there is no Service Recipient account
- Bilingual interface (F-09) is out of scope
- One app instance is assumed. The tablet can open the app over the local Wi-Fi using the Network URL Streamlit prints when it starts

github link: https://github.com/Munity2325/FIT1056-group-project-application
