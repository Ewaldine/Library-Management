from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField, EmailField, DateField
from wtforms.validators import DataRequired, Length, NumberRange, Email, ValidationError
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'library_secret_key_2025'
db = SQLAlchemy(app)

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
    max_books = db.Column(db.Integer, nullable=False, default=5)
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

class LoanForm(FlaskForm):
    book_id = SelectField('Book', coerce=str, validators=[DataRequired()],
                        render_kw={"class": "form-control"})
    member_id = SelectField('Member', coerce=str, validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    due_date = DateField('Due Date', validators=[DataRequired()], format='%Y-%m-%d',
                       render_kw={"class": "form-control", "type": "date"})
    submit = SubmitField('Create Loan', render_kw={"class": "btn btn-success"})

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
    update_overdue_loans()  # Update overdue status
    
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if member:
            active_loans = Loan.query.filter_by(member_id=member.id, return_date=None).all()
            recent_loans = Loan.query.filter_by(member_id=member.id).order_by(Loan.loan_date.desc()).limit(5).all()
            pending_fines = Fine.query.filter_by(member_id=member.id, status='pending').all()
            
            return render_template('dashboard.html', 
                                 title='Member Dashboard',
                                 member=member,
                                 active_loans=active_loans,
                                 recent_loans=recent_loans,
                                 pending_fines=pending_fines)
        else:
            flash('Please complete your member profile.', 'warning')
            return redirect(url_for('profile'))
    
    elif current_user.role == 'librarian':
        # Librarian dashboard
        total_books = Book.query.count()
        total_members = Member.query.count()
        active_loans = Loan.query.filter_by(return_date=None).count()
        overdue_loans = Loan.query.filter_by(status='overdue').count()
        pending_fines = Fine.query.filter_by(status='pending').count()
        
        recent_loans = Loan.query.options(
            joinedload(Loan.book), joinedload(Loan.member)
        ).order_by(Loan.loan_date.desc()).limit(10).all()
        
        return render_template('dashboard.html',
                             title='Librarian Dashboard',
                             total_books=total_books,
                             total_members=total_members,
                             active_loans=active_loans,
                             overdue_loans=overdue_loans,
                             pending_fines=pending_fines,
                             recent_loans=recent_loans)
    
    # Admin dashboard
    total_books = Book.query.count()
    total_members = Member.query.count()
    total_authors = Author.query.count()
    total_publishers = Publisher.query.count()
    
    recent_activities = Loan.query.options(
        joinedload(Loan.book), joinedload(Loan.member)
    ).order_by(Loan.loan_date.desc()).limit(10).all()
    
    return render_template('dashboard.html',
                         title='Admin Dashboard',
                         total_books=total_books,
                         total_members=total_members,
                         total_authors=total_authors,
                         total_publishers=total_publishers,
                         recent_activities=recent_activities)

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
    
    return render_template('books.html', title='Books', books=books, 
                         categories=categories, authors=authors, form=form,
                         search_query=search_query, category_filter=category_filter, author_filter=author_filter)

@app.route('/loans')
@login_required
def loans():
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if member:
            loans = Loan.query.filter_by(member_id=member.id).options(
                joinedload(Loan.book), joinedload(Loan.member)
            ).order_by(Loan.loan_date.desc()).all()
            return render_template('loans.html', title='My Loans', loans=loans, member=member)
    
    else:
        # Admin and librarian view all loans
        status_filter = request.args.get('status', '')
        query = Loan.query.options(joinedload(Loan.book), joinedload(Loan.member))
        
        if status_filter:
            query = query.filter(Loan.status == status_filter)
        
        loans = query.order_by(Loan.loan_date.desc()).all()
        
        # Create form and populate choices for admin/librarian
        form = LoanForm()
        available_books = Book.query.filter(Book.available_copies > 0).all()
        active_members = Member.query.filter(Member.membership_status == 'active').all()
        
        form.book_id.choices = [(b.id, f"{b.id} - {b.title}") for b in available_books]
        form.member_id.choices = [(m.id, f"{m.id} - {m.full_name}") for m in active_members]
        
        return render_template('loans.html', title='Loan Management', loans=loans, form=form)


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
    return render_template('authors.html', title='Authors', authors=authors, form=form)

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
    loan_id = request.json.get('loan_id')
    loan = Loan.query.get(loan_id)
    
    if not loan:
        return jsonify({'success': False, 'message': 'Loan not found'})
    
    # Check permissions
    if current_user.role == 'member':
        member = Member.query.filter_by(user_id=current_user.id).first()
        if loan.member_id != member.id:
            return jsonify({'success': False, 'message': 'Access denied'})
    
    # Check if already returned
    if loan.return_date:
        return jsonify({'success': False, 'message': 'Book already returned'})
    
    # Check renewal limit
    if loan.renewed_count >= loan.max_renewals:
        return jsonify({'success': False, 'message': 'Maximum renewals reached'})
    
    # Check if book has reservations (simplified)
    # In a real system, you'd check if someone else has reserved this book
    
    try:
        # Calculate new due date
        member = Member.query.get(loan.member_id)
        loan_period = get_loan_period(member)
        new_due_date = loan.due_date + timedelta(days=loan_period)
        
        # Update loan
        loan.due_date = new_due_date
        loan.renewed_count += 1
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Loan renewed successfully'})
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
                language=form.language.data,
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
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding book: {str(e)}', 'error')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{getattr(form, field).label.text}: {error}', 'error')
    
    return redirect(url_for('books'))

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