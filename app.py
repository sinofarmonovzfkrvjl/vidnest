from flask import Flask, request, render_template, send_from_directory, redirect, url_for
from flask_admin import Admin, AdminIndexView
import os
import cv2
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_admin.contrib.sqla import ModelView
from flask_wtf import FlaskForm
from wtforms import FileField, StringField, PasswordField, SubmitField, validators
from flask_admin.form.upload import FileUploadField
from flask_login import LoginManager, login_user, logout_user, current_user, UserMixin, login_required

app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = "admin"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["VIDEO_UPLOADS"] = "video_uploads"
app.config["IMAGE_UPLOADS"] = "image_uploads"

class NewIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login"))

# initialize
db = SQLAlchemy(app)
admin = Admin(app, template_mode="bootstrap3", index_view=NewIndexView())

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "you didn't log in, you need to login first"
login_manager.login_message_category = "warning"

# Models

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

    def __str__(self):
        return f"<User {self.name}>"

class PostVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    video = db.Column(db.String(255), nullable=False)

# add views

class PostVideoView(ModelView):
    form_extra_fields = {
        'video': FileUploadField('video', base_path="video_uploads")
    }

    def extract_90sframe(self, video_path, video_name):
        video_cap = cv2.VideoCapture(video_path)
        frame_number = 90
        video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
        success, frame = video_cap.read()
        if success:
            frame_path = os.path.join("image_uploads", f"{video_name}.jpg")
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        else:
            print("Failed to read video")
    def on_model_change(self, form, model, is_created):
        if is_created and model.video:
            video_path = os.path.join("video_uploads", model.video)
            self.extract_90sframe(video_path, model.video)
    
    def on_model_delete(self, model):
        if model.video:
            video_path = f"video_uploads/{model.video}"
            if os.path.exists(video_path):
                os.remove(video_path)
                os.remove(f"image_uploads/{model.video}.jpg")

# Admin

admin.add_view(ModelView(User, db.session))
admin.add_view(PostVideoView(PostVideo, db.session))


# Forms

class LoginForm(FlaskForm):
    name = StringField("Name", validators=[validators.DataRequired()])
    username = StringField("Username", validators=[validators.DataRequired()])
    password = PasswordField("Password", validators=[validators.DataRequired()])
    submit = SubmitField("Login")

class VideoForm(FlaskForm):
    video = FileField("video", validators=[validators.DataRequired()])

with app.app_context():
    db.create_all()

if os.path.exists("image_uploads") == False:
    os.mkdir("image_uploads")

if os.path.exists("video_uploads") == False:
    os.mkdir("video_uploads")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@app.route('/', methods=['GET', 'POST'])
def HomePage():
    if request.method == "POST":
        
        if 'video' not in request.files:
            return "No video uploaded"

        video = request.files['video']

        FILE = f"video_uploads/{video.filename}"

        video.save(FILE)

        video_cap = cv2.VideoCapture(FILE)
        frame_number = 90
        video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
        success, frame = video_cap.read()

        if success:
            cv2.imwrite(f"image_uploads/{video.filename}.jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        else:
            print("Failed to read video")

    imagenames = os.listdir('image_uploads')

    return render_template('index.html', imagenames=imagenames, user=current_user)

@app.route("/videos_uploads/<filename>")
def serve_video(filename):
    return send_from_directory('video_uploads', filename)

@app.route("/thumbnail_uploads/<imagename>/")
def see_image_url(imagename):
    return send_from_directory('image_uploads', imagename)

@app.route("/video/<videoname>/delete")
def delete_video(videoname):
    videoname = ".".join(videoname.split(".")[:-1])
    os.remove(f"video_uploads/{videoname}")
    os.remove(f"image_uploads/{videoname}.jpg")
    return redirect("/", code=302)

@app.route("/watch/<videoname>")
@login_required
def watch(videoname):
    videoname = ".".join(videoname.split(".")[:-1])
    video = PostVideo.query.filter_by(video=videoname).first()
    print(video)
    return render_template("watch.html", videoname=videoname, video=video)

@app.route("/upload")
def upload_video():
    form = VideoForm()
    if form.validate_on_submit():
        title = form.title.data
        video = form.video.data
        video = PostVideo(title=title, video=video)
        db.session.add(video)
        db.session.commit()
        return redirect(url_for("HomePage"))
    return render_template('upload.html', form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        name = form.name.data
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(name=name, username=username, password=password).first()
        if not user:
            user = User(name=name, username=username, password=password)
            db.session.add(user)
            db.session.commit()
        login_user(user)
        return redirect(url_for("HomePage"))
    return render_template("login.html", form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("HomePage"))


if __name__ == "__main__":
    app.run(debug=True)