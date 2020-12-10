import os

from flask import Flask, redirect, render_template, request, url_for
from peewee import BooleanField, CharField, ForeignKeyField, IntegrityError, Model, SqliteDatabase
from playhouse.db_url import connect
import requests

db = connect(os.environ.get('DATABASE_URL'))
# db = SqliteDatabase('smallworld.db')


class BaseModel(Model):
    class Meta:
        database = db


class Insults(BaseModel):
    language = CharField()
    insult = CharField(unique=True)

    class Meta:
        table_name = 'insults'


class Users(BaseModel):
    username = CharField(unique=True)
    password = CharField()
    email = CharField(unique=True)
    logged = BooleanField(default=False)

    class Meta:
        table_name = 'users'


class InsultsUsers(BaseModel):
    user_id = ForeignKeyField(Users)
    insult_id = ForeignKeyField(Insults)

    class Meta:
        table_name = 'insults_users'


TABLES = [
    Insults, InsultsUsers, Users
]

with db.connection_context():
    db.create_tables(TABLES, safe=True)
    db.commit()


app = Flask(__name__)


languages_dict = {'English': 'en', 'Italian': 'it', 'French': 'fr', 'Spanish': 'es', 'Russian': 'ru', 'Swahili': 'sw', 'German': 'de', 'Greek': 'el', 'Chinese': 'cn'}

@app.before_request
def _db_connect():
    db.connect()


@app.teardown_request
def _db_close(_):
    if not db.is_closed():
        db.close()


@app.route('/', methods=['GET'])
def login():
    try:
        if request.method == "GET":
            email = request.args.get("Email")
            if not email:
                return render_template('index.j2')
            password = request.args.get("Password")
            result = Users.select(Users.id).where((Users.email == email) & (Users.password == password)).get()
            result.logged = True
            result.save()
            return redirect(url_for("insults"))
    except Exception:
        return render_template('index.j2', message="This user does not exist, please sign up first")


@app.route('/insults')
def insults():
    language_entered = request.args.get('language')
    if not language_entered:
        return render_template('insults.j2')
    if language_entered not in languages_dict.keys():
        return render_template('insults.j2', not_available="You idiot! I told you to choose a language from the list!")
    language = languages_dict[language_entered]
    resp = requests.get(f'https://evilinsult.com/generate_insult.php?lang={language}&type=json')
    if not resp:
        return render_template('insults.j2')
    resp_json = resp.json()
    the_insult = resp_json['insult']
    try:
        Insults.create(language=language, insult=the_insult)
        insult_id = Insults.select(Insults.id).order_by(Insults.id.desc()).limit(1).get()
        logged_id = Users.select(Users.id).where(Users.logged).get()
        InsultsUsers.create(user_id=logged_id, insult_id=insult_id)
    except IntegrityError:
        pass
    return render_template(
        'insults.j2',
        language=language_entered.title(),
        insult=the_insult,
    )


@app.route('/userinsults')
def userinsults():
    insults = (Insults.select().join(InsultsUsers, on=(InsultsUsers.insult_id == Insults.id)).join(Users, on=(Users.id == InsultsUsers.user_id)).where(Users.logged == 'True').order_by(Insults.language))
    return render_template('userinsults.j2', insult=insults)


@app.route('/deleteinsults')
def deleteinsults():
    take_it_back = Insults.select(Insults.id).order_by(Insults.id).limit(1).get()
    if take_it_back:
        message = "Took your insult Back!"
    else:
        message = ""
    return render_template('deleteinsults.j2', message=message)


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == "POST":
        username = request.form["Username"]
        password = request.form["Password"]
        email = request.form["Email"]
        try:
            Users.create(username=username, password=password, email=email)
        except IntegrityError:
            return render_template('signup.j2', username=username, message="Username or Email not available")
        result = True
        return render_template('signup.j2', result=result, username=username, message="signed up")
    else:
        return render_template('signup.j2', username="", message="")


@app.route('/logout')
def logout():
    logged_id = Users.select(Users.id).where(Users.logged).get()
    logged_id.logged = False
    logged_id.save()
    return redirect(url_for("login"))


if __name__ == '__main__':
    app.run()