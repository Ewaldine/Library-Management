# Library Management System with Carrell Booking
A comprehensive web-based library management system built with Flask that handles book lending, member management, and study carrell (study room) booking functionality.

## Table of Contents
1. Features

2. Technology Stack

3. Installation

4. Configuration

5. Database Models

6. User Roles

7. API Endpoints

8. Usage Guide

9. Fines System

10. Notification System

11. Development

12. Deployment

13. Testing

14. Troubleshooting

15. Contributing

16. License

### 1. Features

##### Core Library Management
* Book Management: Add, edit, delete, and search books with detailed metadata
* Author & Publisher Management: Complete catalog management
* Category System: Hierarchical book categorization
* Member Management: Member registration and profile management
* Loan System: Book borrowing, returns, and renewals
* Fine Management: Automated fine calculation and payment processing
#### Carrell (Study Room) Booking System
* Student Booking Portal: Web-based carrell reservation system
* Time Restrictions: Bookings limited to current week (Monday-Friday)
* Smart Scheduling: Prevents double-booking and time conflicts
* Booking Limits: Maximum 2 carrell bookings per day per member
* Cancellation Policy: Free cancellation up to 1 hour before booking
* Real-time Availability: Live slot availability display
#### Advanced Features
* Multi-role Authentication: Admin, Librarian, and Member roles
* Automated Fines: Late returns, noise violations, and key penalties
* Notification System: Email-style notifications for reminders and fines
* Background Tasks: Automated notification delivery and status updates
* Responsive Design: Mobile-friendly Bootstrap interface
* Search & Filtering: Advanced book and member search capabilities


### 2. Technology Stack
#### Backend
* Python 3.8+
* Flask - Web framework
* SQLAlchemy - ORM and database management
* Flask-Login - User session management
* Flask-WTF - Form handling and validation
* Werkzeug - Password hashing and security
#### Frontend
* Bootstrap 5 - Responsive UI framework
* Font Awesome - Icons
* JavaScript (ES6+) - Client-side interactivity
* HTML5 & CSS3 - Markup and styling
#### Database
* SQLite (Development) - Lightweight file-based database
* PostgreSQL/MySQL (Production) - Recommended for production use
#### Additional Libraries
* ReportLab - PDF report generation
* Threading - Background task processing
* DateTime - Comprehensive date/time handling

### 3. Installation
#### Prerequisites
* Python 3.8 or higher
* pip (Python package manager)
* Virtual environment (recommended)
#### i. Clone the repo
```bash
git clone https://github.com/Ewaldine/Library-Management.git
cd library-management-system
```
#### ii. Create Virtual Environment
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```
#### iii. Install Dependencies
```bash
pip install -r requirements.txt
```
#### iv. Database Setup
```bash
# The database will be automatically created on first run
# For manual setup:
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()
```
#### v. Run the application
```bash
python app.py
```
The application will be available at http://localhost:5000

#### Default Accounts
The system creates default accounts on initial setup
* Admin: admin / admin123
* Librarian: librarian / librarian123

### 4. Configuration
#### Environment Variables
Create a .env file for configuration:
```env
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///library.db

# Email Configuration (for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Application Settings
MAX_BOOKS_PER_MEMBER=5
LOAN_PERIOD_STANDARD=14
LOAN_PERIOD_PREMIUM=28
FINE_PER_DAY=1.00
CARRELL_BOOKING_LIMIT=2
```
#### Application Configuration
Key settings in app.py:
```python
app.config.update(
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///library.db'),
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)
```
### 5. Database Models
#### Core Models
* User: Authentication and role management
* Member: Extended member information and preferences
* Book: Complete book metadata with availability tracking
* Author: Author information and biography
* Publisher: Publisher details
* Category: Hierarchical book categorization

#### Transaction Models
* Loan: Book borrowing records with renewal tracking
* Fine: Financial penalties with payment status
* Carrell: Study room management
* CarrellRental: Carrell booking and usage records
* Notification: User notification system

#### Relationships
```python
# Example relationships
Member → Loans (One-to-Many)
Book → Loans (One-to-Many)  
Author → Books (One-to-Many)
Carrell → CarrellRentals (One-to-Many)
Member → Fines (One-to-Many)
```

### 6. User Roles
#### Member
* View and search book catalog
* Borrow and renew books
* Book study carrells
* View personal loans and fines
* Pay fines online
* Update personal profile
* Receive notifications

#### Librarian
* All member privileges
* Manage book loans and returns
* Process fine payments
* Manage carrell rentals
* Add noise fines
* View member information
* Basic book management

#### Administrator
* All librarian privileges
* Full system management
* User role management
* System configuration
* Database maintenance
* Advanced reporting

### 7. API Endpoints
#### Authentication
* POST /login - User authentication
* POST /register - New member registration
* POST /logout - User logout

#### Book Management
* GET /books - Browse and search books
* POST /add_book - Add new book (Admin/Librarian)
* POST /edit_book - Update book information
* POST /delete_book - Remove book from catalog

#### Loan System
* POST /api/borrow_book - Member book borrowing
* POST /api/return_book - Book return processing
* POST /api/renew_loan - Loan extension
* GET /loans - Loan management interface

#### Carrell System
* GET /student_carrells - Student booking portal
* POST /book_carrell - Create new carrell booking
* POST /cancel_booking - Cancel existing booking
* POST /end_carrell_rental - End active rental (Staff)

#### Fine Management
* POST /api/pay_fine - Process fine payment
* POST /add_noise_fine - Add noise violation fine

### 8. Usage Guide
#### For Members
##### Book Borrowing
###### i. Login to your account
###### ii. Browse available books using search and filters
###### iii. Click "Borrow" on desired books
###### iv. View your active loans in "My Loans" section
###### v. Renew loans before due date (if eligible)
##### Carrell Booking
###### i. Navigate to "Book Carrell" section
###### ii. Select desired date (current week only)
###### iii. Choose available time slot (9 AM - 5 PM)
###### iv. Select carrell and duration (2-3 hours)
###### v. Confirm booking
###### vi. Cancel if needed (up to 1 hour before)
##### Fine Management
###### i. Check "My Fines" for pending amounts
###### ii. Pay fines online to restore borrowing privileges
###### iii. View fine history and receipts
#### For Librarians/Admins
##### Member Management
###### i. Access "Members" section
###### ii. Add new members or edit existing profiles
###### iii. Manage membership status and limits
##### Loan Processing
###### i. Use "Loans" section to manage all borrowings
###### ii. Process book returns
###### iii. Handle renewal requests
###### iv. Monitor overdue items
##### Carrell Management
###### i. Monitor active carrell rentals
###### ii. End rentals and process key returns
###### iii. Add noise fines for violations
###### vi. Manage carrell availability

### 9. Fines System
#### Fine Types and Amounts
* Late Book Returns: $1.00 per day overdue
* Noise Violations: $25.00 per incident
* Late Key Returns: $10.00 flat fee
* Lost/Damaged Items: Variable based on item value

#### Fine Processing
```python
# Automatic fine calculation
def calculate_fine(loan):
    if loan.is_overdue and not loan.return_date:
        days_overdue = loan.days_overdue
        return days_overdue * FINE_PER_DAY
    return 0.0
```
#### Payment Restrictions
* Members with pending fines cannot borrow books
* Members with fines cannot book carrells
* Fine payments are immediately processed

### 10. Notification System
#### Notification Types
* Loan Reminders: Due date approaching
* Overdue Alerts: Books past due date
* Fine Notices: New fines applied
* Carrell Reminders: Booking start and end times
* System Announcements: General updates
#### Delivery System
* In-app Notifications: Real-time alert system
* Scheduled Delivery: Time-based notification triggering
* Background Processing: Automated notification checks
#### Configuration
```python
# Notification scheduling
def schedule_carrell_notifications(rental):
    # Pre-rental reminders
    # During-rental warnings  
    # Post-rental fine notices
```

### 11. Development
#### Project Structure
```text
library-management-system/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── instance/
│   └── library.db        # SQLite database (auto-created)
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── dashboard.html    # Dashboard pages
│   ├── books.html        # Book management
│   ├── loans.html        # Loan management
│   ├── carrells.html     # Staff carrell management
│   ├── student_carrells.html # Student booking portal
│   └── ...              # Other templates
└── static/              # Static assets
    ├── style.css        # Custom styles
    └── ...              # Other static files
```
#### Adding New Features
##### i. Database Changes
```python
# Add new model
class NewFeature(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # ... fields

# Update database
with app.app_context():
    db.create_all()
```
##### ii. Route Implementation
```python
@app.route('/new_feature')
@login_required
def new_feature():
    # Implementation logic
    return render_template('new_feature.html')
```
##### iii. Template Creation
```html
{% extends "base.html" %}
{% block content %}
<!-- Feature implementation -->
{% endblock %}
```
#### Code Standards
* Follow PEP 8 for Python code
* Use meaningful variable and function names
* Include docstrings for all functions
* Write comprehensive comments for complex logic
* Maintain consistent indentation and formatting

### 12. Deployment
#### Production Deployment
##### i. Database Migration
```bash
# For PostgreSQL
export DATABASE_URL=postgresql://username:password@localhost/library

# For MySQL
export DATABASE_URL=mysql://username:password@localhost/library
```
##### ii. Production WSGI Server
```python
# wsgi.py
from app import app

if __name__ == "__main__":
    app.run()
```
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```
##### iii. Web Server Configuration
```nginx
# nginx configuration
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
#### Security Considerations
* Change default secret key in production
* Use HTTPS in production environment
* Implement rate limiting for API endpoints
* Regular security updates for dependencies
* Database backup strategies

### 13. Testing
#### Test Categories
* Unit Tests: Individual component testing
* Integration Tests: Multi-component workflow testing
* User Acceptance Testing: End-to-end user scenarios
#### Sample Test Structure
```python
import unittest
from app import app, db
from models import User, Book, Loan

class LibraryTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
    def test_book_borrowing(self):
        # Test book borrowing workflow
        pass
        
    def test_carrell_booking(self):
        # Test carrell booking restrictions
        pass
```
#### Running Tests
```bash
python -m pytest tests/
python -m unittest discover tests/
```

### 14. Troubleshooting
#### Common Issues
##### i. Database Connection Errors
`solution: Check database URL and file permissions`
##### ii. Import Errors
`Solution: Verify virtual environment activation and requirements installation`
##### iii. Template Not Found
`Solution: Check template file paths and naming`
##### iv. Permission Denied Errors
`Solution: Verify user roles and login status`

#### Debug Mode
Enable debug mode for development:
```python
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)]
```
#### Logs
Application logs are available in:
* Console output (development)
* System logs (production)
* Database error tables

### 15. Contributing
####We welcome contributions! Please follow these steps:
##### i. Fork the repository
##### ii. Create a feature branch (git checkout -b feature/AmazingFeature)
##### iii. Commit your changes (git commit -m 'Add some AmazingFeature')
##### iv. Push to the branch (git push origin feature/AmazingFeature)
##### v. Open a Pull Request
#### Contribution Guidelines
* Write clear, documented code
* Add tests for new functionality
* Update documentation as needed
* Follow existing code style and patterns
* Ensure all tests pass before submitting

### 16. License
```text
MIT License

Copyright (c) 2025 Mbitjita N. Kamapunga, Renathe Kayunde, Ewaldine Eises, Dian Jakob.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
