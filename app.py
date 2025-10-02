from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField, EmailField, DateField
from wtforms.validators import DataRequired, Length, NumberRange, Email, ValidationError
from datetime import datetime, timedelta
from sqlalchemy import and_, case, or_, func
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import threading
import time
import io
import os
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'library_secret_key_2025'
db = SQLAlchemy(app)

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

# Login Manager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models with normalized design
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')  # member, librarian, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def has_role(self, role):
        return self.role == role

class Member(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    membership_type = db.Column(db.String(20), nullable=False, default='standard')  # standard, premium
    membership_status = db.Column(db.String(20), nullable=False, default='active')  # active, suspended, expired
    max_books = db.Column(db.Integer, nullable=False, default=3)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    loans = db.relationship('Loan', backref='member', lazy=True)
    fines = db.relationship('Fine', backref='member', lazy=True)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def current_loans_count(self):
        return Loan.query.filter_by(member_id=self.id, return_date=None).count()
    
    @property
    def total_fines_due(self):
        return db.session.query(func.sum(Fine.amount)).filter(
            Fine.member_id == self.id,
            Fine.paid_date == None
        ).scalar() or 0.0

class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    biography = db.Column(db.Text)
    birth_date = db.Column(db.Date)
    nationality = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    books = db.relationship('Book', backref='author', lazy=True)

class Publisher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    books = db.relationship('Book', backref='publisher', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    parent = db.relationship('Category', remote_side=[id], backref='subcategories')
    books = db.relationship('Book', backref='category', lazy=True)

class Book(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    edition = db.Column(db.String(50))
    publication_year = db.Column(db.Integer)
    pages = db.Column(db.Integer)
    language = db.Column(db.String(50), default='English')
    description = db.Column(db.Text)
    cover_image = db.Column(db.String(200))
    
    # Foreign keys to normalized tables
    author_id = db.Column(db.Integer, db.ForeignKey('author.id'), nullable=False)
    publisher_id = db.Column(db.Integer, db.ForeignKey('publisher.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    location = db.Column(db.String(100))  # Shelf location
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    loans = db.relationship('Loan', backref='book', lazy=True)
    
    @property
    def is_available(self):
        return self.available_copies > 0
    
    @property
    def availability_status(self):
        if self.available_copies > 0:
            return 'Available'
        elif self.available_copies == 0:
            return 'Checked Out'
        else:
            return 'Unknown'

class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.String(10), db.ForeignKey('book.id'), nullable=False)
    member_id = db.Column(db.String(10), db.ForeignKey('member.id'), nullable=False)
    
    loan_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime)
    
    # Status: active, returned, overdue
    status = db.Column(db.String(20), nullable=False, default='active')
    
    renewed_count = db.Column(db.Integer, default=0)
    max_renewals = db.Column(db.Integer, default=2)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    fine = db.relationship('Fine', backref='loan', uselist=False, lazy=True)
    
    @property
    def is_overdue(self):
        if self.return_date:
            return False
        return datetime.utcnow() > self.due_date
    
    @property
    def days_overdue(self):
        if self.return_date or not self.is_overdue:
            return 0
        return (datetime.utcnow() - self.due_date).days

class Fine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'), nullable=False)
    member_id = db.Column(db.String(10), db.ForeignKey('member.id'), nullable=False)
    
    amount = db.Column(db.Float, nullable=False, default=0.0)
    reason = db.Column(db.String(200), nullable=False)  # overdue, damage, lost
    issued_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    paid_date = db.Column(db.DateTime)
    
    # Status: pending, paid, waived
    status = db.Column(db.String(20), nullable=False, default='pending')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Add to models section

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.String(10), db.ForeignKey('member.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # carrell_reminder, carrell_fine, etc.
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    sent_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    member = db.relationship('Member', backref='notifications')





class Carrell(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Carrell A1"
    location = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=1)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Current rental information
    current_rental_id = db.Column(db.Integer, db.ForeignKey('carrell_rental.id'))
    
    # Use primaryjoin to specify the exact relationship
    current_rental = db.relationship('CarrellRental', 
                                   foreign_keys=[current_rental_id],
                                   post_update=True,
                                   backref='current_carrell')


class CarrellRental(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    carrell_id = db.Column(db.String(10), db.ForeignKey('carrell.id'), nullable=False)
    member_id = db.Column(db.String(10), db.ForeignKey('member.id'), nullable=False)
    
    rental_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    scheduled_end_time = db.Column(db.DateTime, nullable=False)
    actual_end_time = db.Column(db.DateTime)
    
    # Status: active, completed, overdue
    status = db.Column(db.String(20), nullable=False, default='active')
    
    # Key management
    key_returned = db.Column(db.Boolean, nullable=False, default=False)
    key_return_time = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - explicitly specify foreign_keys
    carrell = db.relationship('Carrell', 
                            foreign_keys=[carrell_id],
                            backref=db.backref('rentals', lazy=True))
    member = db.relationship('Member', 
                           foreign_keys=[member_id],
                           backref=db.backref('carrell_rentals', lazy=True))

# Update the Fine model to include new fine types
# Add to the existing Fine model (modify the reason choices comment)
# reason: overdue, damage, lost, noise, key_not_returned

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)], 
                          render_kw={"placeholder": "Enter your username", "class": "form-control"})
    password = PasswordField('Password', validators=[DataRequired()], 
                            render_kw={"placeholder": "Enter your password", "class": "form-control"})
    submit = SubmitField('Login', render_kw={"class": "btn btn-primary w-100"})

class MemberRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)],
                          render_kw={"placeholder": "Choose a username", "class": "form-control"})
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)],
                           render_kw={"placeholder": "Enter password", "class": "form-control"})
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)], 
                            render_kw={"placeholder": "Enter first name", "class": "form-control"})
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)], 
                           render_kw={"placeholder": "Enter last name", "class": "form-control"})
    email = EmailField('Email', validators=[DataRequired(), Email(), Length(max=120)], 
                      render_kw={"placeholder": "Enter email address", "class": "form-control"})
    phone = StringField('Phone', validators=[DataRequired(), Length(max=20)], 
                       render_kw={"placeholder": "Enter phone number", "class": "form-control"})
    address = TextAreaField('Address', validators=[DataRequired()],
                          render_kw={"placeholder": "Enter your address", "class": "form-control", "rows": 3})
    membership_type = SelectField('Membership Type', choices=[('standard', 'Standard'), ('premium', 'Premium')],
                                 render_kw={"class": "form-control"})
    submit = SubmitField('Register Member', render_kw={"class": "btn btn-success"})
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

class BookForm(FlaskForm):
    isbn = StringField('ISBN', validators=[DataRequired(), Length(max=20)],
                      render_kw={"placeholder": "Enter ISBN", "class": "form-control"})
    title = StringField('Title', validators=[DataRequired(), Length(max=300)], 
                      render_kw={"placeholder": "Enter book title", "class": "form-control"})
    edition = StringField('Edition', validators=[Length(max=50)],
                        render_kw={"placeholder": "Enter edition", "class": "form-control"})
    publication_year = IntegerField('Publication Year', validators=[NumberRange(min=1000, max=2030)],
                                  render_kw={"placeholder": "Enter publication year", "class": "form-control"})
    pages = IntegerField('Pages', validators=[NumberRange(min=1)],
                       render_kw={"placeholder": "Enter number of pages", "class": "form-control"})
    language = StringField('Language', validators=[Length(max=50)],
                         render_kw={"placeholder": "Enter language", "class": "form-control"})
    description = TextAreaField('Description',
                              render_kw={"placeholder": "Enter book description", "class": "form-control", "rows": 4})
    total_copies = IntegerField('Total Copies', validators=[DataRequired(), NumberRange(min=1)],
                              render_kw={"placeholder": "Enter total copies", "class": "form-control"})
    location = StringField('Location', validators=[Length(max=100)],
                         render_kw={"placeholder": "Enter shelf location", "class": "form-control"})
    
    author_id = SelectField('Author', coerce=int, validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    publisher_id = SelectField('Publisher', coerce=int, validators=[DataRequired()],
                             render_kw={"class": "form-control"})
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()],
                            render_kw={"class": "form-control"})
    
    submit = SubmitField('Add Book', render_kw={"class": "btn btn-success"})

class AuthorForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)], 
                      render_kw={"placeholder": "Enter author name", "class": "form-control"})
    biography = TextAreaField('Biography',
                            render_kw={"placeholder": "Enter author biography", "class": "form-control", "rows": 4})
    birth_date = DateField('Birth Date', format='%Y-%m-%d',
                         render_kw={"class": "form-control", "type": "date"})
    nationality = StringField('Nationality', validators=[Length(max=100)],
                           render_kw={"placeholder": "Enter nationality", "class": "form-control"})
    submit = SubmitField('Add Author', render_kw={"class": "btn btn-success"})
    
    def validate_birth_date(self, field):
        if field.data and field.data > date.today():
            raise ValidationError('Birth date cannot be in the future.')

class PublisherForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=200)], 
                      render_kw={"placeholder": "Enter publisher name", "class": "form-control"})
    address = TextAreaField('Address',
                          render_kw={"placeholder": "Enter publisher address", "class": "form-control", "rows": 3})
    phone = StringField('Phone', validators=[Length(max=20)],
                      render_kw={"placeholder": "Enter phone number", "class": "form-control"})
    email = EmailField('Email', validators=[Email(), Length(max=120)],
                     render_kw={"placeholder": "Enter email address", "class": "form-control"})
    website = StringField('Website', validators=[Length(max=200)],
                        render_kw={"placeholder": "Enter website URL", "class": "form-control"})
    submit = SubmitField('Add Publisher', render_kw={"class": "btn btn-success"})


class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)], 
                      render_kw={"placeholder": "Enter category name", "class": "form-control"})
    description = TextAreaField('Description',
                              render_kw={"placeholder": "Enter category description", "class": "form-control", "rows": 3})
    parent_id = SelectField('Parent Category', 
                          render_kw={"class": "form-control"})
    submit = SubmitField('Add Category', render_kw={"class": "btn btn-success"})

# Add these form definitions to the forms section (after the existing forms)


class LoanForm(FlaskForm):
    book_id = SelectField('Book', coerce=str, validators=[DataRequired()],
                        render_kw={"class": "form-control"})
    member_id = SelectField('Member', coerce=str, validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    due_date = DateField('Due Date', validators=[DataRequired()], format='%Y-%m-%d',
                       render_kw={"class": "form-control", "type": "date"})
    submit = SubmitField('Create Loan', render_kw={"class": "btn btn-success"})
    
    def validate_due_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError('Due date cannot be in the past.')

class CarrellRentalForm(FlaskForm):
    carrell_id = SelectField('Carrell', coerce=str, validators=[DataRequired()],
                           render_kw={"class": "form-control"})
    member_id = SelectField('Member', coerce=str, validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    duration_hours = SelectField('Duration', choices=[(3, '3 Hours')], coerce=int,
                               render_kw={"class": "form-control"})
    submit = SubmitField('Create Rental', render_kw={"class": "btn btn-success"})

class CarrellForm(FlaskForm):
    name = StringField('Carrell Name', validators=[DataRequired(), Length(max=100)],
                      render_kw={"placeholder": "Enter carrell name", "class": "form-control"})
    location = StringField('Location', validators=[DataRequired(), Length(max=200)],
                         render_kw={"placeholder": "Enter location", "class": "form-control"})
    capacity = IntegerField('Capacity', validators=[DataRequired(), NumberRange(min=1)],
                          render_kw={"placeholder": "Enter capacity", "class": "form-control"})
    submit = SubmitField('Add Carrell', render_kw={"class": "btn btn-success"})


# Initialize database
with app.app_context():
    db.create_all()
    
    # Create default admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        
        # Create default librarian
        librarian_user = User(
            username='librarian',
            password_hash=generate_password_hash('librarian123'),
            role='librarian'
        )
        db.session.add(librarian_user)
        db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions
def calculate_fine(loan):
    """Calculate fine for an overdue loan"""
    if not loan.is_overdue or loan.return_date:
        return 0.0
    
    days_overdue = loan.days_overdue
    fine_per_day = 1.0  # $1 per day
    return round(days_overdue * fine_per_day, 2)


# Add these helper functions after the existing helper functions

def schedule_carrell_notifications(rental):
    """Schedule all notifications for a carrell rental"""
    try:
        # Calculate notification times
        scheduled_end = rental.scheduled_end_time
        one_hour_before = scheduled_end - timedelta(hours=1)
        thirty_min_before = scheduled_end - timedelta(minutes=30)
        at_due_time = scheduled_end
        
        # Schedule notifications
        notifications = [
            {
                'time': one_hour_before,
                'title': 'Carrell Rental Reminder - 1 Hour Left',
                'message': f'Your carrell rental for {rental.carrell.name} will expire in 1 hour. Please return the key on time to avoid fines.',
                'type': 'carrell_reminder_1h'
            },
            {
                'time': thirty_min_before,
                'title': 'Carrell Rental Reminder - 30 Minutes Left',
                'message': f'Your carrell rental for {rental.carrell.name} will expire in 30 minutes. Please prepare to return the key.',
                'type': 'carrell_reminder_30m'
            },
            {
                'time': at_due_time,
                'title': 'Carrell Rental Expired - Fine Incurred',
                'message': f'Your carrell rental for {rental.carrell.name} has expired. A $10 fine has been applied for late key return.',
                'type': 'carrell_fine_notice'
            }
        ]
        
        # Create notification records
        for notif in notifications:
            notification = Notification(
                member_id=rental.member_id,
                title=notif['title'],
                message=notif['message'],
                notification_type=notif['type'],
                scheduled_time=notif['time']
            )
            db.session.add(notification)
        
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error scheduling notifications: {str(e)}")
        return False

def send_notification(notification):
    """Send a notification (simulate email/SMS)"""
    try:
        # In a real system, you would:
        # 1. Send email
        # 2. Send SMS
        # 3. Send push notification
        
        # For now, we'll just mark it as sent and print to console
        notification.sent_time = datetime.utcnow()
        db.session.commit()
        
        print(f"Notification sent to {notification.member.full_name}: {notification.title}")
        return True
        
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
        return False

def check_pending_notifications():
    """Check and send pending notifications (to be called periodically)"""
    try:
        now = datetime.utcnow()
        pending_notifications = Notification.query.filter(
            Notification.scheduled_time <= now,
            Notification.sent_time == None
        ).all()
        
        for notification in pending_notifications:
            send_notification(notification)
            
        return len(pending_notifications)
        
    except Exception as e:
        print(f"Error checking pending notifications: {str(e)}")
        return 0

def update_overdue_loans():
    """Update status of overdue loans and create fines"""
    overdue_loans = Loan.query.filter(
        Loan.return_date == None,
        Loan.due_date < datetime.utcnow(),
        Loan.status == 'active'
    ).all()
    
    for loan in overdue_loans:
        loan.status = 'overdue'
        
        # Check if fine already exists
        existing_fine = Fine.query.filter_by(loan_id=loan.id).first()
        if not existing_fine:
            fine_amount = calculate_fine(loan)
            if fine_amount > 0:
                new_fine = Fine(
                    loan_id=loan.id,
                    member_id=loan.member_id,
                    amount=fine_amount,
                    reason='overdue'
                )
                db.session.add(new_fine)
    
    db.session.commit()

def get_loan_period(member):
    """Get loan period based on membership type"""
    if member.membership_type == 'premium':
        return 28  # 4 weeks
    return 14  # 2 weeks

# Routes
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    update_overdue_loans()
    
    # Add this line to get current datetime
    current_time = datetime.utcnow()
    
    if current_user.role == 'member':
        # Single query with eager loading
        member = Member.query.options(
            joinedload(Member.loans).joinedload(Loan.book),
            joinedload(Member.fines)
        ).filter_by(user_id=current_user.id).first()
        
        if member:
            # Use pre-calculated fields instead of properties
            active_loans = [loan for loan in member.loans if loan.return_date is None]
            recent_loans = sorted(member.loans, key=lambda x: x.loan_date, reverse=True)[:5]
            pending_fines = [fine for fine in member.fines if fine.status == 'pending']
            
            return render_template('dashboard.html', 
                                 title='Member Dashboard',
                                 member=member,
                                 active_loans=active_loans,
                                 recent_loans=recent_loans,
                                 pending_fines=pending_fines,
                                 now=current_time)  # Add this line
        else:
            flash('Please complete your member profile.', 'warning')
            return redirect(url_for('profile'))
    
    elif current_user.role == 'librarian':
        # Optimized queries with single aggregate calls
        total_books = db.session.query(func.count(Book.id)).scalar()
        total_members = db.session.query(func.count(Member.id)).scalar()
        active_loans = db.session.query(func.count(Loan.id)).filter(
            Loan.return_date == None
        ).scalar()
        overdue_loans = db.session.query(func.count(Loan.id)).filter(
            Loan.status == 'overdue'
        ).scalar()
        pending_fines = db.session.query(func.count(Fine.id)).filter(
            Fine.status == 'pending'
        ).scalar()
        
        # Limited recent loans with eager loading
        recent_loans = Loan.query.options(
            joinedload(Loan.book),
            joinedload(Loan.member)
        ).order_by(Loan.loan_date.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                             title='Librarian Dashboard',
                             total_books=total_books,
                             total_members=total_members,
                             active_loans=active_loans,
                             overdue_loans=overdue_loans,
                             pending_fines=pending_fines,
                             recent_loans=recent_loans,
                             now=current_time)  # Add this line
    
    # Admin dashboard - optimized queries
    total_books = db.session.query(func.count(Book.id)).scalar()
    total_members = db.session.query(func.count(Member.id)).scalar()
    total_authors = db.session.query(func.count(Author.id)).scalar()
    total_publishers = db.session.query(func.count(Publisher.id)).scalar()
    
    recent_activities = Loan.query.options(
        joinedload(Loan.book),
        joinedload(Loan.member)
    ).order_by(Loan.loan_date.desc()).limit(5).all()
    
    return render_template('dashboard.html',
                         title='Admin Dashboard',
                         total_books=total_books,
                         total_members=total_members,
                         total_authors=total_authors,
                         total_publishers=total_publishers,
                         recent_activities=recent_activities,
                         now=current_time)  # Add this line

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        form = MemberRegistrationForm()
        
        # Remove password field for profile updates
        del form.password
        
        if request.method == 'GET' and member:
            form.first_name.data = member.first_name
            form.last_name.data = member.last_name
            form.email.data = member.email
            form.phone.data = member.phone
            form.address.data = member.address
            form.membership_type.data = member.membership_type
        
        if form.validate_on_submit():
            try:
                if member:
                    # Update existing member
                    member.first_name = form.first_name.data
                    member.last_name = form.last_name.data
                    member.email = form.email.data
                    member.phone = form.phone.data
                    member.address = form.address.data
                    member.membership_type = form.membership_type.data
                else:
                    # Create new member
                    member_count = Member.query.count()
                    new_id = f'M{member_count + 1:06d}'
                    
                    new_member = Member(
                        id=new_id,
                        first_name=form.first_name.data,
                        last_name=form.last_name.data,
                        email=form.email.data,
                        phone=form.phone.data,
                        address=form.address.data,
                        membership_type=form.membership_type.data,
                        user_id=current_user.id
                    )
                    db.session.add(new_member)
                
                db.session.commit()
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating profile: {str(e)}', 'error')
        
        return render_template('profile.html', title='Member Profile', form=form, member=member)
    
    # Admin and librarian don't need profiles
    flash('Admin and librarian users do not have a profile page.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html', title='Login', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = MemberRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'error')
        else:
            try:
                hashed_password = generate_password_hash(form.password.data)
                new_user = User(username=form.username.data, password_hash=hashed_password, role='member')
                db.session.add(new_user)
                db.session.flush()  # Get user ID
                
                # Create member record
                member_count = Member.query.count()
                new_id = f'M{member_count + 1:06d}'
                
                new_member = Member(
                    id=new_id,
                    first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    email=form.email.data,
                    phone=form.phone.data,
                    address=form.address.data,
                    membership_type=form.membership_type.data,
                    user_id=new_user.id
                )
                db.session.add(new_member)
                db.session.commit()
                
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error during registration: {str(e)}', 'error')
    return render_template('register.html', title='Register', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/members')
@login_required
def members():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    members = Member.query.all()
    form = MemberRegistrationForm()
    return render_template('members.html', title='Members', members=members, form=form)

@app.route('/books')
@login_required
def books():
    search_query = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    author_filter = request.args.get('author', '')
    
    query = Book.query.options(joinedload(Book.author), joinedload(Book.publisher), joinedload(Book.category))
    
    if search_query:
        query = query.filter(Book.title.ilike(f'%{search_query}%'))
    
    if category_filter:
        query = query.filter(Book.category_id == category_filter)
    
    if author_filter:
        query = query.filter(Book.author_id == author_filter)
    
    books = query.all()
    categories = Category.query.all()
    authors = Author.query.all()
    
    form = BookForm()
    form.author_id.choices = [(a.id, a.name) for a in authors]
    form.publisher_id.choices = [(p.id, p.name) for p in Publisher.query.all()]
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    current_year = datetime.now().year  # Add this line
    
    return render_template('books.html', title='Books', books=books, 
                         categories=categories, authors=authors, form=form,
                         search_query=search_query, category_filter=category_filter, 
                         author_filter=author_filter, current_year=current_year)  # Add current_year here

@app.route('/edit_book', methods=['POST'])
@login_required
def edit_book():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        book_id = request.form.get('book_id')
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'message': 'Book not found'})
        
        # Update book details
        book.isbn = request.form.get('isbn')
        book.title = request.form.get('title')
        book.edition = request.form.get('edition')
        
        # Handle integer fields
        publication_year = request.form.get('publication_year')
        book.publication_year = int(publication_year) if publication_year else None
        
        pages = request.form.get('pages')
        book.pages = int(pages) if pages else None
        
        book.author_id = int(request.form.get('author_id'))
        book.publisher_id = int(request.form.get('publisher_id'))
        book.category_id = int(request.form.get('category_id'))
        book.description = request.form.get('description')
        
        # Update total copies and adjust available copies if needed
        new_total_copies = int(request.form.get('total_copies'))
        if new_total_copies < book.total_copies:
            # If reducing total copies, make sure we don't go below currently borrowed copies
            borrowed_copies = book.total_copies - book.available_copies
            if new_total_copies < borrowed_copies:
                return jsonify({'success': False, 'message': f'Cannot reduce total copies below {borrowed_copies} (currently borrowed)'})
        
        book.total_copies = new_total_copies
        book.available_copies = book.total_copies - (book.total_copies - book.available_copies)
        book.location = request.form.get('location')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Book updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating book: {str(e)}'})

@app.route('/delete_book', methods=['POST'])
@login_required
def delete_book():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        book_id = request.json.get('book_id')
        book = Book.query.get(book_id)
        
        if not book:
            return jsonify({'success': False, 'message': 'Book not found'})
        
        # Check if book has active loans
        active_loans = Loan.query.filter_by(book_id=book_id, return_date=None).count()
        if active_loans > 0:
            return jsonify({'success': False, 'message': f'Cannot delete book with {active_loans} active loan(s)'})
        
        db.session.delete(book)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Book deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting book: {str(e)}'})

@app.route('/loans')
@login_required
def loans():
    form = LoanForm()
    loans = Loan.query.options(joinedload(Loan.book), joinedload(Loan.member)).all()

    member = None
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()

    return render_template(
        'loans.html',
        title='Loan Management',
        loans=loans,
        form=form,
        member=member  
    )

@app.route('/loan_details')
@login_required
def loan_details():
    if current_user.role != 'member':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    book_id = request.args.get('book_id')
    member_id = request.args.get('member_id')
    
    # Verify the member owns these loans
    member = Member.query.filter_by(user_id=current_user.id).first()
    if not member or member.id != member_id:
        flash('Access denied', 'error')
        return redirect(url_for('loans'))
    
    # Get all individual loans for this book
    loans_list = Loan.query.filter_by(
        book_id=book_id, 
        member_id=member_id
    ).order_by(Loan.loan_date.desc()).all()
    
    book = Book.query.get(book_id)
    
    # Count active loans for this book
    active_loans_count = sum(1 for loan in loans_list if loan.return_date is None)
    
    return render_template('loan_details.html', 
                         book=book, 
                         loans=loans_list, 
                         active_loans_count=active_loans_count)

@app.route('/get_loan_id')
@login_required
def get_loan_id():
    if current_user.role != 'member':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    book_id = request.args.get('book_id')
    member_id = request.args.get('member_id')
    
    # Verify the member owns this loan
    member = Member.query.filter_by(user_id=current_user.id).first()
    if not member or member.id != member_id:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    # Get the active loan for this book
    loan = Loan.query.filter_by(
        book_id=book_id, 
        member_id=member_id,
        return_date=None
    ).first()
    
    if loan:
        return jsonify({'success': True, 'loan_id': loan.id})
    else:
        return jsonify({'success': False, 'message': 'No active loan found'})

@app.route('/fines')
@login_required
def fines():
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if member:
            fines = Fine.query.filter_by(member_id=member.id).options(
                joinedload(Fine.loan).joinedload(Loan.book)
            ).order_by(Fine.issued_date.desc()).all()
            return render_template('fines.html', title='My Fines', fines=fines, member=member)
    
    else:
        # Admin and librarian view all fines
        status_filter = request.args.get('status', '')
        query = Fine.query.options(
            joinedload(Fine.member), joinedload(Fine.loan).joinedload(Loan.book)
        )
        
        if status_filter:
            query = query.filter(Fine.status == status_filter)
        
        fines = query.order_by(Fine.issued_date.desc()).all()
        return render_template('fines.html', title='Fine Management', fines=fines)

@app.route('/authors')
@login_required
def authors():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    authors = Author.query.all()
    form = AuthorForm()
    current_date = date.today().isoformat()  # Add this line
    
    return render_template('authors.html', title='Authors', authors=authors, form=form, current_date=current_date)

@app.route('/publishers')
@login_required
def publishers():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    publishers = Publisher.query.all()
    form = PublisherForm()
    return render_template('publishers.html', title='Publishers', publishers=publishers, form=form)

@app.route('/categories')
@login_required
def categories():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    categories = Category.query.all()
    form = CategoryForm()
    form.parent_id.choices = [('', 'No Parent')] + [(c.id, c.name) for c in categories]
    return render_template('categories.html', title='Categories', categories=categories, form=form)

# API Routes for AJAX operations
@app.route('/api/borrow_book', methods=['POST'])
@login_required
def borrow_book():
    if current_user.role != 'member':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    member = Member.query.filter_by(user_id=current_user.id).first()
    book_id = request.json.get('book_id')
    book = Book.query.get(book_id)
    
    if not book:
        return jsonify({'success': False, 'message': 'Book not found'})
    
    # Check if book is available
    if not book.is_available:
        return jsonify({'success': False, 'message': 'Book is not available'})
    
    # Check member's current loans
    if member.current_loans_count >= member.max_books:
        return jsonify({'success': False, 'message': f'You have reached your limit of {member.max_books} books'})
    
    # Check if member has pending fines
    if member.total_fines_due > 0:
        return jsonify({'success': False, 'message': 'You have pending fines. Please clear them first.'})
    
    try:
        # Calculate due date based on membership type
        loan_period = get_loan_period(member)
        due_date = datetime.utcnow() + timedelta(days=loan_period)
        
        # Create loan
        new_loan = Loan(
            book_id=book_id,
            member_id=member.id,
            due_date=due_date
        )
        db.session.add(new_loan)
        
        # Update book availability
        book.available_copies -= 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Book borrowed successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error borrowing book: {str(e)}'})

@app.route('/api/return_book', methods=['POST'])
@login_required
def return_book():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    loan_id = request.json.get('loan_id')
    loan = Loan.query.get(loan_id)
    
    if not loan:
        return jsonify({'success': False, 'message': 'Loan not found'})
    
    if loan.return_date:
        return jsonify({'success': False, 'message': 'Book already returned'})
    
    try:
        # Update loan
        loan.return_date = datetime.utcnow()
        loan.status = 'returned'
        
        # Update book availability
        book = Book.query.get(loan.book_id)
        book.available_copies += 1
        
        # Update fine if exists
        fine = Fine.query.filter_by(loan_id=loan_id).first()
        if fine and fine.status == 'pending':
            fine.amount = calculate_fine(loan)  # Recalculate final amount
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Book returned successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error returning book: {str(e)}'})

@app.route('/api/renew_loan', methods=['POST'])
@login_required
def renew_loan():
    if current_user.role != 'member':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    loan_id = request.json.get('loan_id')
    loan = Loan.query.get(loan_id)
    
    if not loan:
        return jsonify({'success': False, 'message': 'Loan not found'})
    
    if loan.member.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    if loan.return_date:
        return jsonify({'success': False, 'message': 'Book already returned'})
    
    if loan.renewed_count >= loan.max_renewals:
        return jsonify({'success': False, 'message': 'Maximum renewals reached'})
    
    if loan.is_overdue:
        return jsonify({'success': False, 'message': 'Cannot renew overdue book'})
    
    # NEW: Check if member has multiple copies of this book
    same_book_loans_count = Loan.query.filter(
        Loan.member_id == loan.member_id,
        Loan.book_id == loan.book_id,
        Loan.return_date.is_(None)
    ).count()
    
    if same_book_loans_count > 1:
        return jsonify({'success': False, 'message': 'Cannot renew when you have multiple copies of the same book'})
    
    try:
        # Calculate new due date (extend by original loan period)
        member = Member.query.filter_by(user_id=current_user.id).first()
        loan_period = get_loan_period(member)
        loan.due_date = loan.due_date + timedelta(days=loan_period)
        loan.renewed_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Loan renewed successfully', 'new_due_date': loan.due_date.strftime('%Y-%m-%d')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error renewing loan: {str(e)}'})

@app.route('/api/pay_fine', methods=['POST'])
@login_required
def pay_fine():
    fine_id = request.json.get('fine_id')
    fine = Fine.query.get(fine_id)
    
    if not fine:
        return jsonify({'success': False, 'message': 'Fine not found'})
    
    # Check permissions
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if fine.member_id != member.id:
            return jsonify({'success': False, 'message': 'Access denied'})
    
    if fine.status == 'paid':
        return jsonify({'success': False, 'message': 'Fine already paid'})
    
    try:
        # In a real system, you'd integrate with a payment gateway
        # For now, we'll just mark it as paid
        fine.status = 'paid'
        fine.paid_date = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Fine paid successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error paying fine: {str(e)}'})

# Add to routes section

# In the carrells route, update the active_rentals query
@app.route('/carrells')
@login_required
def carrells():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    carrells_list = Carrell.query.all()
    active_rentals = CarrellRental.query.filter_by(status='active').options(
        joinedload(CarrellRental.member), 
        joinedload(CarrellRental.carrell)
    ).all()
    
    form = CarrellForm()
    rental_form = CarrellRentalForm()
    
    # Update choices
    available_carrells = Carrell.query.filter_by(is_available=True).all()
    active_members = Member.query.filter_by(membership_status='active').all()
    
    rental_form.carrell_id.choices = [(c.id, f"{c.name} - {c.location}") for c in available_carrells]
    rental_form.member_id.choices = [(m.id, f"{m.id} - {m.full_name}") for m in active_members]
    
    return render_template('carrells.html', 
                         title='Carrell Management',
                         carrells=carrells_list,
                         active_rentals=active_rentals,
                         form=form,
                         rental_form=rental_form)

@app.route('/add_carrell', methods=['POST'])
@login_required
def add_carrell():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = CarrellForm()
    if form.validate_on_submit():
        try:
            # Generate carrell ID
            carrell_count = Carrell.query.count()
            new_id = f'C{carrell_count + 1:04d}'
            
            new_carrell = Carrell(
                id=new_id,
                name=form.name.data,
                location=form.location.data,
                capacity=form.capacity.data
            )
            db.session.add(new_carrell)
            db.session.commit()
            
            flash('Carrell added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding carrell: {str(e)}', 'error')
    
    return redirect(url_for('carrells'))

# Add these new routes

@app.route('/notifications')
@login_required
def notifications():
    """Display user notifications"""
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if not member:
            flash('Member profile not found', 'error')
            return redirect(url_for('dashboard'))
        
        user_notifications = Notification.query.filter_by(
            member_id=member.id
        ).order_by(Notification.created_at.desc()).all()
        
        return render_template('notifications.html', 
                             title='My Notifications',
                             notifications=user_notifications)
    
    else:
        flash('This page is for members only', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/notifications/count')
@login_required
def notification_count():
    """Get unread notification count for current user"""
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if member:
            count = Notification.query.filter_by(
                member_id=member.id,
                is_read=False
            ).count()
            return jsonify({'count': count})
    
    return jsonify({'count': 0})

@app.route('/api/notifications/mark_read', methods=['POST'])
@login_required
def mark_notification_read():
    """Mark a notification as read"""
    notification_id = request.json.get('notification_id')
    
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if member:
            notification = Notification.query.filter_by(
                id=notification_id,
                member_id=member.id
            ).first()
            
            if notification:
                notification.is_read = True
                db.session.commit()
                return jsonify({'success': True})
    
    return jsonify({'success': False})

def background_notification_checker():
    """Background thread to check for pending notifications"""
    while True:
        try:
            count = check_pending_notifications()
            if count > 0:
                print(f"Sent {count} notifications")
            time.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Error in background notification checker: {str(e)}")
            time.sleep(60)

# Start the background thread when the app starts
def start_background_tasks():
    """Start background tasks"""
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        thread = threading.Thread(target=background_notification_checker, daemon=True)
        thread.start()

# Call this after app initialization
with app.app_context():
    db.create_all()
    
    # Create default admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        
        # Create default librarian
        librarian_user = User(
            username='librarian',
            password_hash=generate_password_hash('librarian123'),
            role='librarian'
        )
        db.session.add(librarian_user)
        db.session.commit()
    
    # Start background tasks
    start_background_tasks()

@app.route('/api/check_notifications')
@login_required
def check_notifications_api():
    """API endpoint to check and send pending notifications"""
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        count = check_pending_notifications()
        return jsonify({'success': True, 'notifications_sent': count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Update the create_carrell_rental function
@app.route('/create_carrell_rental', methods=['POST'])
@login_required
def create_carrell_rental():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = CarrellRentalForm()
    
    # Update choices dynamically
    available_carrells = Carrell.query.filter_by(is_available=True).all()
    active_members = Member.query.filter_by(membership_status='active').all()
    
    form.carrell_id.choices = [(c.id, f"{c.name} - {c.location}") for c in available_carrells]
    form.member_id.choices = [(m.id, f"{m.id} - {m.full_name}") for m in active_members]
    
    if form.validate_on_submit():
        carrell_id = form.carrell_id.data
        member_id = form.member_id.data
        duration_hours = form.duration_hours.data
        
        carrell = Carrell.query.get(carrell_id)
        member = Member.query.get(member_id)
        
        if not carrell or not member:
            flash('Carrell or member not found', 'error')
            return redirect(url_for('carrells'))
        
        if not carrell.is_available:
            flash('Carrell is not available', 'error')
            return redirect(url_for('carrells'))
        
        try:
            # Calculate end time
            start_time = datetime.utcnow()
            end_time = start_time + timedelta(hours=duration_hours)
            
            # Create rental
            new_rental = CarrellRental(
                carrell_id=carrell_id,
                member_id=member_id,
                scheduled_end_time=end_time
            )
            db.session.add(new_rental)
            db.session.flush()  # Get the rental ID
            
            # Update carrell availability
            carrell.is_available = False
            carrell.current_rental_id = new_rental.id
            
            # Schedule notifications
            schedule_carrell_notifications(new_rental)
            
            db.session.commit()
            flash('Carrell rental created successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating carrell rental: {str(e)}', 'error')
    
    return redirect(url_for('carrells'))

# Update the end_carrell_rental function
@app.route('/end_carrell_rental', methods=['POST'])
@login_required
def end_carrell_rental():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        rental_id = request.json.get('rental_id')
        key_returned = request.json.get('key_returned', True)
        
        rental = CarrellRental.query.get(rental_id)
        if not rental:
            return jsonify({'success': False, 'message': 'Rental not found'})
        
        # Update rental
        rental.actual_end_time = datetime.utcnow()
        rental.status = 'completed'
        rental.key_returned = key_returned
        rental.key_return_time = datetime.utcnow() if key_returned else None
        
        # Update carrell availability
        carrell = Carrell.query.get(rental.carrell_id)
        carrell.is_available = True
        carrell.current_rental_id = None
        
        # Check for key return fine
        if not key_returned:
            key_fine = Fine(
                member_id=rental.member_id,
                amount=10.00,  # $10 fine for not returning key
                reason='key_not_returned',
                issued_date=datetime.utcnow()
            )
            db.session.add(key_fine)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Carrell rental ended successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error ending rental: {str(e)}'})


@app.route('/add_noise_fine', methods=['POST'])
@login_required
def add_noise_fine():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        member_id = request.json.get('member_id')
        amount = 25.00  # $25 fine for noise
        
        member = Member.query.get(member_id)
        if not member:
            return jsonify({'success': False, 'message': 'Member not found'})
        
        # Check if member has an active carrell rental
        active_rental = CarrellRental.query.filter_by(
            member_id=member_id, 
            status='active'
        ).first()
        
        if not active_rental:
            return jsonify({'success': False, 'message': 'Member does not have an active carrell rental'})
        
        # Create noise fine
        noise_fine = Fine(
            member_id=member_id,
            amount=amount,
            reason='noise',
            issued_date=datetime.utcnow()
        )
        db.session.add(noise_fine)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Noise fine of ${amount:.2f} added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error adding noise fine: {str(e)}'})

# Administrative Routes
@app.route('/add_member', methods=['POST'])
@login_required
def add_member():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = MemberRegistrationForm()
    if form.validate_on_submit():
        try:
            # Generate member ID
            member_count = Member.query.count()
            new_id = f'M{member_count + 1:06d}'
            
            # Create user account
            user = User(
                username=form.username.data,
                password_hash=generate_password_hash(form.password.data),
                role='member'
            )
            db.session.add(user)
            db.session.flush()  # Get user ID
            
            # Create member record
            new_member = Member(
                id=new_id,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                email=form.email.data,
                phone=form.phone.data,
                address=form.address.data,
                membership_type=form.membership_type.data,
                user_id=user.id
            )
            db.session.add(new_member)
            db.session.commit()
            
            flash(f'Member added successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding member: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('members'))

# Add these routes to your app.py

@app.route('/edit_member', methods=['POST'])
@login_required
def edit_member():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        member_id = request.form.get('member_id')
        member = Member.query.get(member_id)
        
        if not member:
            return jsonify({'success': False, 'message': 'Member not found'})
        
        # Update member details
        member.first_name = request.form.get('first_name')
        member.last_name = request.form.get('last_name')
        member.email = request.form.get('email')
        member.phone = request.form.get('phone')
        member.address = request.form.get('address')
        member.membership_type = request.form.get('membership_type')
        member.membership_status = request.form.get('membership_status')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Member updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating member: {str(e)}'})

@app.route('/edit_publisher', methods=['POST'])
@login_required
def edit_publisher():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        publisher_id = request.form.get('publisher_id')
        publisher = Publisher.query.get(publisher_id)
        
        if not publisher:
            return jsonify({'success': False, 'message': 'Publisher not found'})
        
        # Update publisher details
        publisher.name = request.form.get('name')
        publisher.email = request.form.get('email')
        publisher.phone = request.form.get('phone')
        publisher.address = request.form.get('address')
        publisher.website = request.form.get('website')
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Publisher updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating publisher: {str(e)}'})

@app.route('/edit_category', methods=['POST'])
@login_required
def edit_category():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        category_id = request.form.get('category_id')
        category = Category.query.get(category_id)
        
        if not category:
            return jsonify({'success': False, 'message': 'Category not found'})
        
        # Update category details
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        
        # Handle parent_id
        parent_id = request.form.get('parent_id')
        category.parent_id = int(parent_id) if parent_id else None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Category updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating category: {str(e)}'})

@app.route('/add_book', methods=['POST'])
@login_required
def add_book():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = BookForm()
    authors = Author.query.all()
    publishers = Publisher.query.all()
    categories = Category.query.all()
    
    form.author_id.choices = [(a.id, a.name) for a in authors]
    form.publisher_id.choices = [(p.id, p.name) for p in publishers]
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    if form.validate_on_submit():
        try:
            # Check if ISBN already exists
            existing_book = Book.query.filter_by(isbn=form.isbn.data).first()
            if existing_book:
                flash(f'A book with ISBN "{form.isbn.data}" already exists. Please use a different ISBN.', 'error')
                # Re-render the template with form data preserved
                return render_template('books.html', 
                                    title='Books', 
                                    books=Book.query.options(joinedload(Book.author), joinedload(Book.publisher), joinedload(Book.category)).all(),
                                    categories=categories, 
                                    authors=authors, 
                                    form=form,
                                    search_query='', 
                                    category_filter='', 
                                    author_filter='', 
                                    current_year=datetime.now().year)
            
            # Generate book ID
            book_count = Book.query.count()
            new_id = f'B{book_count + 1:06d}'
            
            new_book = Book(
                id=new_id,
                isbn=form.isbn.data,
                title=form.title.data,
                edition=form.edition.data,
                publication_year=form.publication_year.data,
                pages=form.pages.data,
                language=form.language.data or 'English',
                description=form.description.data,
                total_copies=form.total_copies.data,
                available_copies=form.total_copies.data,  # Initially all copies are available
                location=form.location.data,
                author_id=form.author_id.data,
                publisher_id=form.publisher_id.data,
                category_id=form.category_id.data
            )
            db.session.add(new_book)
            db.session.commit()
            
            flash('Book added successfully', 'success')
            return redirect(url_for('books'))
            
        except Exception as e:
            db.session.rollback()
            # Check if it's a unique constraint violation for ISBN
            if 'UNIQUE constraint failed: book.isbn' in str(e):
                flash(f'A book with ISBN "{form.isbn.data}" already exists. Please use a different ISBN.', 'error')
            else:
                flash(f'Error adding book: {str(e)}', 'error')
            
            # Re-render the template with form data preserved
            return render_template('books.html', 
                                title='Books', 
                                books=Book.query.options(joinedload(Book.author), joinedload(Book.publisher), joinedload(Book.category)).all(),
                                categories=categories, 
                                authors=authors, 
                                form=form,
                                search_query='', 
                                category_filter='', 
                                author_filter='', 
                                current_year=datetime.now().year)
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    # If form validation fails, redirect back to books page but we need to preserve form data
    # This is handled by the form object itself which retains the submitted data
    books_list = Book.query.options(joinedload(Book.author), joinedload(Book.publisher), joinedload(Book.category)).all()
    return render_template('books.html', 
                         title='Books', 
                         books=books_list,
                         categories=categories, 
                         authors=authors, 
                         form=form,
                         search_query='', 
                         category_filter='', 
                         author_filter='', 
                         current_year=datetime.now().year)

@app.route('/add_author', methods=['POST'])
@login_required
def add_author():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = AuthorForm()
    if form.validate_on_submit():
        try:
            new_author = Author(
                name=form.name.data,
                biography=form.biography.data,
                birth_date=form.birth_date.data,
                nationality=form.nationality.data
            )
            db.session.add(new_author)
            db.session.commit()
            
            flash('Author added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding author: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('authors'))

@app.route('/add_publisher', methods=['POST'])
@login_required
def add_publisher():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = PublisherForm()
    if form.validate_on_submit():
        try:
            new_publisher = Publisher(
                name=form.name.data,
                address=form.address.data,
                phone=form.phone.data,
                email=form.email.data,
                website=form.website.data
            )
            db.session.add(new_publisher)
            db.session.commit()
            
            flash('Publisher added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding publisher: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('publishers'))

@app.route('/add_category', methods=['POST'])
@login_required
def add_category():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = CategoryForm()
    categories = Category.query.all()
    form.parent_id.choices = [('', 'No Parent')] + [(str(c.id), c.name) for c in categories]
    
    if form.validate_on_submit():
        try:
            parent_id = form.parent_id.data
            # Convert to int if not empty, otherwise set to None
            parent_id = int(parent_id) if parent_id else None
            
            new_category = Category(
                name=form.name.data,
                description=form.description.data,
                parent_id=parent_id
            )
            db.session.add(new_category)
            db.session.commit()
            
            flash('Category added successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding category: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('categories'))

@app.route('/edit_author', methods=['POST'])
@login_required
def edit_author():
    if current_user.role not in ['admin', 'librarian']:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        author_id = request.form.get('author_id')
        author = Author.query.get(author_id)
        
        if not author:
            return jsonify({'success': False, 'message': 'Author not found'})
        
        # Update author details
        author.name = request.form.get('name')
        author.nationality = request.form.get('nationality')
        author.biography = request.form.get('biography')
        
        # Handle birth date
        birth_date_str = request.form.get('birth_date')
        if birth_date_str:
            author.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            # Validate birth date is not in future
            if author.birth_date > date.today():
                return jsonify({'success': False, 'message': 'Birth date cannot be in the future'})
        else:
            author.birth_date = None
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Author updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating author: {str(e)}'})



@app.route('/create_loan', methods=['POST'])
@login_required
def create_loan():
    if current_user.role not in ['admin', 'librarian']:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))
    
    form = LoanForm()
    
    # Update choices dynamically
    available_books = Book.query.filter(Book.available_copies > 0).all()
    active_members = Member.query.filter(Member.membership_status == 'active').all()
    
    form.book_id.choices = [(b.id, f"{b.id} - {b.title}") for b in available_books]
    form.member_id.choices = [(m.id, f"{m.id} - {m.full_name}") for m in active_members]
    
    if form.validate_on_submit():
        book_id = form.book_id.data
        member_id = form.member_id.data
        due_date = form.due_date.data
        
        book = Book.query.get(book_id)
        member = Member.query.get(member_id)
        
        if not book or not member:
            flash('Book or member not found', 'error')
            return redirect(url_for('loans'))
        
        # Check if book is available
        if not book.is_available:
            flash('Book is not available', 'error')
            return redirect(url_for('loans'))
        
        # Check member's current loans
        if member.current_loans_count >= member.max_books:
            flash(f'Member has reached their limit of {member.max_books} books', 'error')
            return redirect(url_for('loans'))
        
        # Check if member has pending fines
        if member.total_fines_due > 0:
            flash('Member has pending fines. Please clear them first.', 'error')
            return redirect(url_for('loans'))
        
        try:
            # Create loan
            new_loan = Loan(
                book_id=book_id,
                member_id=member_id,
                due_date=due_date
            )
            db.session.add(new_loan)
            
            # Update book availability
            book.available_copies -= 1
            
            db.session.commit()
            flash('Loan created successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating loan: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('loans'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 