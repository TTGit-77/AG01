from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Change this to a random secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)  # This will store the hashed password
    username = db.Column(db.String(150), nullable=True)  # Optional display name

class Theatre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    total_screens = db.Column(db.Integer, nullable=False, default=3)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    director = db.Column(db.String(100), nullable=False)
    release_year = db.Column(db.Integer, nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    poster_url = db.Column(db.String(200), nullable=False)
    showtimes = db.relationship('Showtime', backref='movie', lazy=True)

class Showtime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    theatre_id = db.Column(db.Integer, db.ForeignKey('theatre.id'), nullable=False)
    show_date = db.Column(db.String(20), nullable=False)
    show_time = db.Column(db.String(10), nullable=False)
    screen = db.Column(db.String(10), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False, default=40)
    booked_seats = db.Column(db.String(200), nullable=False, default='')  # comma-separated seat numbers
    theatre = db.relationship('Theatre', backref='showtimes')

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    showtime_id = db.Column(db.Integer, db.ForeignKey('showtime.id'), nullable=False)
    seats = db.Column(db.String(100), nullable=False)  # comma-separated seat numbers
    booking_time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    showtime = db.relationship('Showtime', backref='bookings')
    user = db.relationship('User', backref='bookings')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('landing.html')

@app.route('/home')
@login_required
def home():
    movies = Movie.query.all()
    # Get theatre info for each movie by checking their showtimes
    movie_theatres = {}
    for movie in movies:
        showtimes = Showtime.query.filter_by(movie_id=movie.id).options(db.joinedload(Showtime.theatre)).all()
        theatres = list(set([s.theatre.name for s in showtimes if s.theatre]))
        movie_theatres[movie.id] = theatres[:2]  # Show max 2 theatres
    return render_template('index.html', movies=movies, movie_theatres=movie_theatres)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form.get('username', email.split('@')[0])  # Use email prefix as default username
        
        # Validate Gmail address
        if not email.endswith('@gmail.com'):
            flash('Please use a Gmail address')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/movie/<int:movie_id>')
@login_required
def movie_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    showtimes = Showtime.query.filter_by(movie_id=movie.id).options(db.joinedload(Showtime.theatre)).all()
    return render_template('movie_details.html', movie=movie, showtimes=showtimes)

@app.route('/book_seats/<int:showtime_id>', methods=['GET', 'POST'])
@login_required
def book_seats(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    booked = showtime.booked_seats.split(',') if showtime.booked_seats else []
    total_seats = showtime.total_seats
    seat_numbers = [str(i+1) for i in range(total_seats)]

    if request.method == 'POST':
        selected_seats = request.form.getlist('seats')
        # Prevent double-booking
        if any(seat in booked for seat in selected_seats):
            flash('Some selected seats are already booked. Please choose different seats.')
            return redirect(url_for('book_seats', showtime_id=showtime_id))
        # Update booked seats
        all_booked = booked + selected_seats
        showtime.booked_seats = ','.join(all_booked)
        booking = Booking(user_id=current_user.id, showtime_id=showtime.id, seats=','.join(selected_seats))
        db.session.add(booking)
        db.session.commit()
        flash('Booking successful!')
        return redirect(url_for('movie_details', movie_id=showtime.movie_id))
    return render_template('book_seats.html', showtime=showtime, seat_numbers=seat_numbers, booked=booked)

from sqlalchemy.orm import joinedload

@app.route('/my_bookings')
@login_required
def my_bookings():
    month = request.args.get('month')
    query = Booking.query.filter_by(user_id=current_user.id)
    if month:
        # Filter by month (YYYY-MM)
        query = query.filter(db.extract('year', Booking.booking_time) == int(month[:4]),
                            db.extract('month', Booking.booking_time) == int(month[5:7]))
    bookings = query.order_by(Booking.booking_time.desc()).all()
    # Get all months with bookings for dropdown
    all_months = db.session.query(db.func.strftime('%Y-%m', Booking.booking_time)).filter_by(user_id=current_user.id).distinct().all()
    all_months = [m[0] for m in all_months]
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    return render_template('my_bookings.html', bookings=bookings, all_months=all_months, selected_month=month, now=now)

@app.route('/profile')
@login_required
def profile():
    total_tickets = db.session.query(func.count(Booking.id)).filter_by(user_id=current_user.id).scalar() or 0
    # Assume Rs. 200 per ticket (each seat)
    bookings = Booking.query.filter_by(user_id=current_user.id).all()
    total_seats = sum(len(b.seats.split(',')) for b in bookings)
    total_amount = total_seats * 200
    return render_template('profile.html', total_tickets=total_seats, total_amount=total_amount)

@app.route('/delete_booking/<int:booking_id>', methods=['POST'])
@login_required
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        abort(403)
    db.session.delete(booking)
    db.session.commit()
    flash('Booking deleted successfully.', 'success')
    return redirect(url_for('my_bookings'))

@app.route('/delete_multiple_bookings', methods=['POST'])
@login_required
def delete_multiple_bookings():
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    ids = request.form.getlist('delete_ids')
    deleted = 0
    for bid in ids:
        booking = Booking.query.get(bid)
        if booking and booking.user_id == current_user.id:
            showtime_dt = booking.showtime.show_date + ' ' + booking.showtime.show_time
            if showtime_dt < now:
                db.session.delete(booking)
                deleted += 1
    db.session.commit()
    if deleted:
        flash(f'{deleted} booking(s) deleted.', 'success')
    else:
        flash('No bookings deleted.', 'warning')
    return redirect(url_for('my_bookings'))

# --- Theatre Owner Panel ---
@app.route('/theatre/login', methods=['GET', 'POST'])
def theatre_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        theatre = Theatre.query.filter_by(email=email).first()
        if theatre and check_password_hash(theatre.password, password):
            session['theatre_logged_in'] = theatre.id
            session['theatre_name'] = theatre.name
            flash(f'Welcome {theatre.owner_name}!')
            return redirect(url_for('theatre_dashboard'))
        flash('Invalid theatre credentials')
    return render_template('theatre_login.html')

@app.route('/theatre/logout')
def theatre_logout():
    session.pop('theatre_logged_in', None)
    session.pop('theatre_name', None)
    flash('Logged out from theatre panel.')
    return redirect(url_for('theatre_login'))

def theatre_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('theatre_logged_in'):
            return redirect(url_for('theatre_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/theatre')
@theatre_required
def theatre_dashboard():
    theatre_id = session.get('theatre_logged_in')
    theatre = Theatre.query.get(theatre_id)
    movies = Movie.query.all()
    showtimes = Showtime.query.filter_by(theatre_id=theatre_id).all()
    bookings = Booking.query.join(Showtime).filter(Showtime.theatre_id == theatre_id).all()
    
    # Get unique movies for this theatre
    unique_movie_ids = set([s.movie_id for s in showtimes])
    total_movies = len(unique_movie_ids)
    total_showtimes = len(showtimes)
    total_bookings = len(bookings)
    # Calculate revenue based on actual booked seats
    total_seats_booked = sum(len(booking.seats.split(',')) for booking in bookings)
    revenue = total_seats_booked * 200
    # Theatre's total seat capacity (fixed capacity based on screens)
    total_seat_capacity = theatre.total_screens * 40  # Assuming 40 seats per screen
    
    return render_template('theatre_dashboard.html', 
                         theatre=theatre, movies=movies, showtimes=showtimes, 
                         bookings=bookings, total_movies=total_movies,
                         total_showtimes=total_showtimes, total_bookings=total_bookings,
                         revenue=revenue, total_seat_capacity=total_seat_capacity,
                         total_seats_booked=total_seats_booked)

@app.route('/theatre/add_movie', methods=['POST'])
@theatre_required
def theatre_add_movie():
    title = request.form['title']
    director = request.form['director']
    release_year = int(request.form['release_year'])
    genre = request.form['genre']
    rating = float(request.form['rating'])
    poster_url = request.form['poster_url']
    
    movie = Movie(title=title, director=director, release_year=release_year,
                  genre=genre, rating=rating, poster_url=poster_url)
    db.session.add(movie)
    db.session.commit()
    flash('Movie added successfully!')
    return redirect(url_for('theatre_dashboard'))

@app.route('/theatre/add_showtime', methods=['POST'])
@theatre_required
def theatre_add_showtime():
    theatre_id = session.get('theatre_logged_in')
    movie_id = int(request.form['movie_id'])
    show_date = request.form['show_date']
    show_time = request.form['show_time']
    screen = request.form['screen']
    
    showtime = Showtime(movie_id=movie_id, theatre_id=theatre_id, 
                       show_date=show_date, show_time=show_time, screen=screen)
    db.session.add(showtime)
    db.session.commit()
    flash('Showtime added successfully!')
    return redirect(url_for('theatre_dashboard'))

@app.route('/theatre/edit_movie/<int:movie_id>', methods=['POST'])
@theatre_required
def theatre_edit_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    movie.title = request.form['title']
    movie.director = request.form['director']
    movie.release_year = int(request.form['release_year'])
    movie.genre = request.form['genre']
    movie.rating = float(request.form['rating'])
    movie.poster_url = request.form['poster_url']
    db.session.commit()
    flash('Movie updated successfully!')
    return redirect(url_for('theatre_dashboard'))

@app.route('/theatre/delete_movie/<int:movie_id>', methods=['POST'])
@theatre_required
def theatre_delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    # Delete all showtimes for this movie at this theatre
    theatre_id = session.get('theatre_logged_in')
    showtimes = Showtime.query.filter_by(movie_id=movie_id, theatre_id=theatre_id).all()
    for showtime in showtimes:
        # Delete bookings for each showtime
        bookings = Booking.query.filter_by(showtime_id=showtime.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(showtime)
    db.session.commit()
    flash('Movie and associated showtimes deleted successfully!')
    return redirect(url_for('theatre_dashboard'))

@app.route('/theatre/edit_showtime/<int:showtime_id>', methods=['POST'])
@theatre_required
def theatre_edit_showtime(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    # Check if this showtime belongs to the current theatre
    if showtime.theatre_id != session.get('theatre_logged_in'):
        flash('Unauthorized access!')
        return redirect(url_for('theatre_dashboard'))
    
    showtime.movie_id = int(request.form['movie_id'])
    showtime.show_date = request.form['show_date']
    showtime.show_time = request.form['show_time']
    showtime.screen = request.form['screen']
    showtime.total_seats = int(request.form['total_seats'])
    db.session.commit()
    flash('Showtime updated successfully!')
    return redirect(url_for('theatre_dashboard'))

@app.route('/theatre/delete_showtime/<int:showtime_id>', methods=['POST'])
@theatre_required
def theatre_delete_showtime(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    # Check if this showtime belongs to the current theatre
    if showtime.theatre_id != session.get('theatre_logged_in'):
        flash('Unauthorized access!')
        return redirect(url_for('theatre_dashboard'))
    
    # Delete associated bookings first
    bookings = Booking.query.filter_by(showtime_id=showtime_id).all()
    for booking in bookings:
        db.session.delete(booking)
    
    db.session.delete(showtime)
    db.session.commit()
    flash('Showtime deleted successfully!')
    return redirect(url_for('theatre_dashboard'))

# --- Admin Panel ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            flash('Admin login successful!')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out from admin panel.')
    return redirect(url_for('admin_login'))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_dashboard():
    movies = Movie.query.all()
    users = User.query.all()
    theatres = Theatre.query.all()
    bookings = Booking.query.all()
    total_users = len(users)
    total_theatres = len(theatres)
    total_bookings = len(bookings)
    total_revenue = len(bookings) * 200  # Assuming Rs. 200 per ticket
    return render_template('admin_dashboard.html', 
                         movies=movies, 
                         users=users,
                         theatres=theatres,
                         bookings=bookings,
                         total_theatres=total_theatres, 
                         total_users=total_users,
                         total_bookings=total_bookings,
                         total_revenue=total_revenue)

@app.route('/admin/add_movie', methods=['POST'])
@admin_required
def admin_add_movie():
    title = request.form['title']
    director = request.form['director']
    release_year = request.form['release_year']
    genre = request.form['genre']
    rating = request.form['rating']
    poster_url = request.form['poster_url']
    # Force correct poster for specific movies
    if title.strip().lower() == 'inception':
        poster_url = 'https://flxt.tmsimg.com/assets/p7825626_p_v8_af.jpg'
    elif title.strip().lower() == 'the dark knight':
        poster_url = 'https://m.media-amazon.com/images/S/pv-target-images/e9a43e647b2ca70e75a3c0af046c4dfdcd712380889779cbdc2c57d94ab63902.jpg'
    elif title.strip().lower() == 'pulp fiction':
        poster_url = 'https://image.tmdb.org/t/p/original/n29q4PmwmrxKBPX2grAvFXyYXYV.jpg'
    new_movie = Movie(title=title, director=director, release_year=release_year, genre=genre, rating=rating, poster_url=poster_url)
    db.session.add(new_movie)
    db.session.commit()
    flash('Movie added successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_movie/<int:movie_id>', methods=['POST'])
@admin_required
def admin_edit_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    movie.title = request.form['title']
    movie.director = request.form['director']
    movie.release_year = request.form['release_year']
    movie.genre = request.form['genre']
    movie.rating = request.form['rating']
    poster_url = request.form['poster_url']
    # Force correct poster for specific movies
    if movie.title.strip().lower() == 'inception':
        movie.poster_url = 'https://flxt.tmsimg.com/assets/p7825626_p_v8_af.jpg'
    elif movie.title.strip().lower() == 'the dark knight':
        movie.poster_url = 'https://m.media-amazon.com/images/S/pv-target-images/e9a43e647b2ca70e75a3c0af046c4dfdcd712380889779cbdc2c57d94ab63902.jpg'
    elif movie.title.strip().lower() == 'pulp fiction':
        movie.poster_url = 'https://image.tmdb.org/t/p/original/n29q4PmwmrxKBPX2grAvFXyYXYV.jpg'
    else:
        movie.poster_url = poster_url
    db.session.commit()
    flash('Movie updated successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_movie/<int:movie_id>', methods=['POST'])
@admin_required
def admin_delete_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    
    # First delete all associated showtimes
    showtimes = Showtime.query.filter_by(movie_id=movie_id).all()
    for showtime in showtimes:
        # Delete all bookings for this showtime
        bookings = Booking.query.filter_by(showtime_id=showtime.id).all()
        for booking in bookings:
            db.session.delete(booking)
        # Delete the showtime
        db.session.delete(showtime)
    
    # Now delete the movie
    db.session.delete(movie)
    db.session.commit()
    flash('Movie and all associated data deleted successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/showtimes/<int:movie_id>', methods=['GET', 'POST'])
@admin_required
def admin_manage_showtimes(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if request.method == 'POST':
        show_date = request.form['show_date']
        show_time = request.form['show_time']
        screen = request.form['screen']
        total_seats = request.form['total_seats']
        new_showtime = Showtime(movie_id=movie.id, show_date=show_date, show_time=show_time, screen=screen, total_seats=total_seats, booked_seats='')
        db.session.add(new_showtime)
        db.session.commit()
        flash('Showtime added!')
        return redirect(url_for('admin_manage_showtimes', movie_id=movie.id))
    showtimes = Showtime.query.filter_by(movie_id=movie.id).all()
    return render_template('admin_showtimes.html', movie=movie, showtimes=showtimes)

@app.route('/admin/edit_showtime/<int:showtime_id>', methods=['POST'])
@admin_required
def admin_edit_showtime(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    showtime.show_date = request.form['show_date']
    showtime.show_time = request.form['show_time']
    showtime.screen = request.form['screen']
    showtime.total_seats = request.form['total_seats']
    db.session.commit()
    flash('Showtime updated!')
    return redirect(url_for('admin_manage_showtimes', movie_id=showtime.movie_id))

@app.route('/admin/delete_showtime/<int:showtime_id>', methods=['POST'])
@admin_required
def admin_delete_showtime(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    movie_id = showtime.movie_id
    db.session.delete(showtime)
    db.session.commit()
    flash('Showtime deleted!')
    return redirect(url_for('admin_manage_showtimes', movie_id=movie_id))

@app.route('/admin/add_theatre', methods=['POST'])
@admin_required
def admin_add_theatre():
    name = request.form['name']
    location = request.form['location']
    owner_name = request.form['owner_name']
    email = request.form['email']
    password = request.form['password']
    phone = request.form['phone']
    total_screens = int(request.form['total_screens'])
    
    hashed_password = generate_password_hash(password)
    theatre = Theatre(name=name, location=location, owner_name=owner_name,
                     email=email, password=hashed_password, phone=phone,
                     total_screens=total_screens)
    db.session.add(theatre)
    db.session.commit()
    flash('Theatre added successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_theatre/<int:theatre_id>', methods=['POST'])
@admin_required
def admin_delete_theatre(theatre_id):
    theatre = Theatre.query.get_or_404(theatre_id)
    
    # Delete all associated showtimes and bookings
    showtimes = Showtime.query.filter_by(theatre_id=theatre_id).all()
    for showtime in showtimes:
        bookings = Booking.query.filter_by(showtime_id=showtime.id).all()
        for booking in bookings:
            db.session.delete(booking)
        db.session.delete(showtime)
    
    db.session.delete(theatre)
    db.session.commit()
    flash('Theatre and all associated data deleted successfully!')
    return redirect(url_for('admin_dashboard'))

@app.route('/create_test_user')
def create_test_user():
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(email='test@gmail.com').first():
        u = User(email='test@gmail.com', username='test', password=generate_password_hash('test123'))
        db.session.add(u)
        db.session.commit()
        return 'Test user created! Email: test@gmail.com, Password: test123'
    return 'Test user already exists.'

def migrate_database():
    """Migrate existing database to new schema without deleting data"""
    with app.app_context():
        try:
            # Add email column if it doesn't exist
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE user ADD COLUMN email VARCHAR(150)'))
                conn.commit()
            print("✓ Added email column to user table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("✓ Email column already exists")
            else:
                print(f"Note: {e}")
        
        try:
            # Add theatre_id column to showtime table if it doesn't exist
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE showtime ADD COLUMN theatre_id INTEGER'))
                conn.commit()
            print("✓ Added theatre_id column to showtime table")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("✓ Theatre_id column already exists")
            else:
                print(f"Note: {e}")
        
        try:
            # Update existing users to have Gmail addresses
            with db.engine.connect() as conn:
                result = conn.execute(db.text('SELECT id, username FROM user WHERE email IS NULL OR email = ""'))
                users = result.fetchall()
                
                for user_id, username in users:
                    email = f"{username}@gmail.com"
                    conn.execute(db.text('UPDATE user SET email = :email WHERE id = :user_id'), 
                               {'email': email, 'user_id': user_id})
                conn.commit()
                
            if users:
                print(f"✓ Migrated {len(users)} existing users to Gmail format")
        except Exception as e:
            print(f"Migration note: {e}")
        
        try:
            # Update existing showtimes to have theatre_id (set to 1 for default theatre)
            with db.engine.connect() as conn:
                result = conn.execute(db.text('SELECT id FROM showtime WHERE theatre_id IS NULL'))
                showtimes = result.fetchall()
                
                if showtimes:
                    # Ensure default theatre exists
                    theatre_result = conn.execute(db.text('SELECT id FROM theatre LIMIT 1'))
                    theatre = theatre_result.fetchone()
                    
                    if theatre:
                        theatre_id = theatre[0]
                        for showtime_id, in showtimes:
                            conn.execute(db.text('UPDATE showtime SET theatre_id = :theatre_id WHERE id = :showtime_id'), 
                                       {'theatre_id': theatre_id, 'showtime_id': showtime_id})
                        conn.commit()
                        print(f"✓ Updated {len(showtimes)} existing showtimes with theatre_id")
        except Exception as e:
            print(f"Showtime migration note: {e}")

if __name__ == '__main__':
    from datetime import datetime, timedelta
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Run migration
        migrate_database()
        
        # Create test user with Gmail if not exists
        try:
            if not User.query.filter_by(email='test@gmail.com').first():
                test_user = User(
                    email='test@gmail.com',
                    username='test',
                    password=generate_password_hash('test123')
                )
                db.session.add(test_user)
                db.session.commit()
                print("✓ Test user created: test@gmail.com / test123")
        except:
            print("✓ Test user already exists")
        
        # Add sample movies if database is empty
        if not Movie.query.first():
            sample_movies = [
                Movie(title='Inception', director='Christopher Nolan', release_year=2010, genre='Sci-Fi', rating=8.8, poster_url='https://flxt.tmsimg.com/assets/p7825626_p_v8_af.jpg'),
                Movie(title='The Dark Knight', director='Christopher Nolan', release_year=2008, genre='Action', rating=9.0, poster_url='https://m.media-amazon.com/images/S/pv-target-images/e9a43e647b2ca70e75a3c0af046c4dfdcd712380889779cbdc2c57d94ab63902.jpg'),
                Movie(title='Pulp Fiction', director='Quentin Tarantino', release_year=1994, genre='Crime', rating=8.9, poster_url='https://image.tmdb.org/t/p/original/n29q4PmwmrxKBPX2grAvFXyYXYV.jpg')
            ]
            db.session.bulk_save_objects(sample_movies)
            db.session.commit()
            print("✓ Sample movies added")
        
        # Create default theatre if none exists
        if not Theatre.query.first():
            default_theatre = Theatre(
                name='CineMax Theatre',
                location='Downtown Plaza, Main Street',
                owner_name='Admin Theatre',
                email='theatre@cinemax.com',
                password=generate_password_hash('theatre123'),
                phone='+91-9876543210',
                total_screens=3
            )
            db.session.add(default_theatre)
            db.session.commit()
            print("✓ Default theatre created")
        
        # Add sample showtimes with theatre_id
        default_theatre = Theatre.query.first()
        for movie in Movie.query.all():
            if not Showtime.query.filter_by(movie_id=movie.id).first():
                for i in range(3):
                    show_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                    show_time = f"{18+i}:00"
                    screen = f"Screen {i+1}"
                    showtime = Showtime(movie_id=movie.id, theatre_id=default_theatre.id, 
                                      show_date=show_date, show_time=show_time, 
                                      screen=screen, total_seats=40, booked_seats='')
                    db.session.add(showtime)
        db.session.commit()
        
        print("🎬 CineBook is ready!")
        print("📧 Gmail authentication enabled")
        print("🗄️  Database viewable in DB Browser for SQLite at: instance/database.db")
    
    app.run(debug=True)
