from backend import logger, app, db
import models
from flask import Flask, flash, redirect, url_for, request, render_template
from flask.ext.admin import Admin, expose, AdminIndexView, helpers
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext import login
from wtforms import form, fields, validators


# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    email = fields.TextField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        if user.password != hash(self.password.data):
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        return db.session.query(models.User).filter_by(email=self.email.data).first()


class RegistrationForm(form.Form):
    email = fields.TextField(validators=[validators.required(), validators.email()])
    password = fields.PasswordField(
        validators=[
            validators.required(),
            validators.length(min=6, message="Your password needs to have at least six characters.")
        ]
    )

    def validate_login(self, field):
        if db.session.query(models.User).filter_by(email=self.email.data).count() > 0:
            raise validators.ValidationError('Duplicate users')


class MyModelView(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    page_size = 50
    column_exclude_list = []

    def is_accessible(self):
        return login.current_user.is_authenticated()


class UserView(MyModelView):
    can_create = False
    column_list = ['email', 'is_admin', 'activated']
    column_exclude_list = ['password']
    form_excluded_columns = ['password', 'procurements_added', 'procurements_approved']

    def is_accessible(self):
        return login.current_user.is_authenticated() and login.current_user.is_admin


# Customized index view that handles login & registration
class HomeView(AdminIndexView):

    @expose('/')
    def index(self):
        if not login.current_user.is_authenticated():
            return redirect(url_for('.login_view'))
        return self.render('admin/home.html')
        # return render_template('admin/home.html')

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        # handle user login
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            if user:
                if not user.is_active():
                    flash('Your account has not been activated. Please contact the site administrator.' , 'error')
                    return redirect(url_for('.login_view'))
                else:
                    login.login_user(user)
            else:
                flash('Username or Password is invalid' , 'error')
                return redirect(url_for('.login_view'))

        if login.current_user.is_authenticated():
            return redirect(url_for('.index'))
        link = '<p>Don\'t have an account? <a href="' + url_for('.register_view') + '">Click here to register.</a></p>'

        return self.render('admin/home.html', form=form, link=link)

    @expose('/register/', methods=('GET', 'POST'))
    def register_view(self):
        form = RegistrationForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = models.User()

            # hash password, before populating User object
            form.password.data = hash(form.password.data)
            form.populate_obj(user)

            # activate the admin user
            if user.email == app.config['ADMIN_USER']:
                user.is_admin = True
                user.activated = True

            db.session.add(user)
            db.session.commit()

            flash('Please wait for your new account to be activated.', 'info')
            return redirect(url_for('.login_view'))
        link = '<p>Already have an account? <a href="' + url_for('.login_view') + '">Click here to log in.</a></p>'
        return self.render('admin/home.html', form=form, link=link, register=True)

    @expose('/logout/')
    def logout_view(self):
        login.logout_user()
        return redirect(url_for('.index'))


# Initialize flask-login
def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = ".login_view"

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(models.User).get(user_id)

init_login()

admin = Admin(app, name='Med-DB', base_template='admin/my_master.html', index_view=HomeView(name='Home'))

admin.add_view(UserView(models.User, db.session, name="Users", endpoint='user'))