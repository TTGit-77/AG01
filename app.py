from flask import Flask, render_template, redirect, url_for, request, flash, session
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
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)  # This will store the hashed password

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
    show_date = db.Column(db.String(20), nullable=False)
    show_time = db.Column(db.String(10), nullable=False)
    screen = db.Column(db.String(10), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False, default=40)
    booked_seats = db.Column(db.String(200), nullable=False, default='')  # comma-separated seat numbers

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    showtime_id = db.Column(db.Integer, db.ForeignKey('showtime.id'), nullable=False)
    seats = db.Column(db.String(100), nullable=False)  # comma-separated seat numbers
    booking_time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    showtime = db.relationship('Showtime', backref='bookings')

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
    return render_template('index.html', movies=movies)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    showtimes = Showtime.query.filter_by(movie_id=movie.id).all()
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
    return render_template('admin_dashboard.html', movies=movies)

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
    db.session.delete(movie)
    db.session.commit()
    flash('Movie deleted successfully!')
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

@app.route('/create_xyz_user')
def create_xyz_user():
    from werkzeug.security import generate_password_hash
    if not User.query.filter_by(username='xyz').first():
        u = User(username='xyz', password=generate_password_hash('xyz'))
        db.session.add(u)
        db.session.commit()
        return 'User xyz created!'
    return 'User xyz already exists.'

if __name__ == '__main__':
    from datetime import datetime, timedelta
    with app.app_context():
        db.create_all()
        # Add some sample movies if the database is empty
        if not Movie.query.first():
            sample_movies = [
                Movie(title='Inception', director='Christopher Nolan', release_year=2010, genre='Sci-Fi', rating=8.8, poster_url='https://flxt.tmsimg.com/assets/p7825626_p_v8_af.jpg'),
                Movie(title='The Dark Knight', director='Christopher Nolan', release_year=2008, genre='Action', rating=9.0, poster_url='https://m.media-amazon.com/images/S/pv-target-images/e9a43e647b2ca70e75a3c0af046c4dfdcd712380889779cbdc2c57d94ab63902.jpg'),
                Movie(title='Pulp Fiction', director='Quentin Tarantino', release_year=1994, genre='Crime', rating=8.9, poster_url='https://image.tmdb.org/t/p/original/n29q4PmwmrxKBPX2grAvFXyYXYV.jpg')
            ]
            db.session.bulk_save_objects(sample_movies)
            db.session.commit()
        # Add sample showtimes for all movies if they don't have any
        for movie in Movie.query.all():
            if not Showtime.query.filter_by(movie_id=movie.id).first():
                for i in range(3):
                    show_date = (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d')
                    show_time = f"{18+i}:00"
                    screen = f"Screen {i+1}"
                    showtime = Showtime(movie_id=movie.id, show_date=show_date, show_time=show_time, screen=screen, total_seats=40, booked_seats='')
                    db.session.add(showtime)
        db.session.commit()
    app.run(debug=True)
