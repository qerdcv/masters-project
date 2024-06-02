import datetime
import os
import json
import shutil
import time
import typing as t

from flask.json import jsonify
from flask import Flask, render_template, send_file, request
from flask_sock import Sock, Server, ConnectionClosed
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from flask_caching import Cache
from werkzeug.exceptions import Forbidden
from werkzeug.utils import secure_filename
from pylti1p3.contrib.flask import FlaskOIDCLogin, FlaskMessageLaunch, FlaskRequest, FlaskCacheDataStorage
from pylti1p3.grade import Grade
from pylti1p3.lineitem import LineItem
from pylti1p3.tool_config import ToolConfJsonFile
from pylti1p3.registration import Registration

from temp import make_temp_dir

app = Flask("lti-imim-22-1", template_folder="templates", static_folder="static")

app.config.from_mapping({
    "DEBUG": True,
    "ENV": "development",
    "CACHE_TYPE": "FileSystemCache",
    "CACHE_DIR": make_temp_dir("cache"),
    "CACHE_DEFAULT_TIMEOUT": 600,
    "SECRET_KEY": "replace-me",
    "SESSION_TYPE": "filesystem",
    "SESSION_FILE_DIR": make_temp_dir("session"),
    "SESSION_COOKIE_NAME": "lti-imim-22-1-sessionid",
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SECURE": True,
    "SESSION_COOKIE_SAMESITE": "None",
    "DEBUG_TB_INTERCEPT_REDIRECTS": False,
    "SOCK_SERVER_OPTIONS": {
        "ping_interval": 25
    },
    "MEDIA_ROOT": "/var/lti/media",
    "SQLALCHEMY_DATABASE_URI": "sqlite:///" + os.path.join('/var/lti', 'database.db'),
    "SQLALCHEMY_TRACK_MODIFICATIONS": False
})

sock = Sock(app)
db = SQLAlchemy(app)
cache = Cache(app)
migrate = Migrate(app, db)

PAGE_TITLE = "LTI"

# alias to get config path
def get_lti_config_path():
    return os.path.join(app.root_path, "..", "configs", "lti.json")


# alias to get flask`s app cache storage
def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)


# returns jwk keys from config
def get_jwk_from_public_key(key_name):
    key_path = os.path.join(app.root_path, "configs", key_name)
    f = open(key_path, "r")
    key_content = f.read()
    jwk = Registration.get_jwk(key_content)
    f.close()
    return jwk


class Task(db.Model):
    __tablename__ = 'task'

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    tests = db.relationship('Test', backref='task', passive_deletes=True)


class Test(db.Model):
    __tablename__ = 'test'

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    # task = db.relationship('Task', backref=db.backref('task'), passive_deletes=True)
    file_name = db.Column(db.String(255), nullable=False)


# returns json web token key set
@app.route("/jwks/", methods=["GET"])
def get_jwks():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify(tool_conf.get_jwks())


# login is used to authorize user that comes from the LMS
@app.route("/login/", methods=["GET", "POST"])
def login():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    launch_data_storage = get_launch_data_storage()

    flask_request = FlaskRequest()
    target_link_uri = flask_request.get_param("target_link_uri")
    if not target_link_uri:
        raise Exception("Missing 'target_link_uri' param")

    oidc_login = FlaskOIDCLogin(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    return oidc_login \
        .enable_check_cookies() \
        .redirect(target_link_uri)


# Main route.
# this route is used to render main template for teacher and student
# it has bunch of parameters that gets in (check message_launch data type for more information)
@app.route("/", methods=["POST"])
def launch():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    message_launch_data = message_launch.get_launch_data()
    task_id = message_launch_data["https://purl.imsglobal.org/spec/lti/claim/resource_link"]["id"]
    tpl_kwargs = {
        "page_title": PAGE_TITLE,
        "is_deep_link_launch": message_launch.is_deep_link_launch(),
        "launch_data": message_launch.get_launch_data(),
        "launch_id": message_launch.get_launch_id(),
        "email": message_launch_data.get("email", ""),
        "task_id": task_id,
    }

    task = db.session.get(Task, task_id)
    tpl_kwargs.update({
        "task": task
    })

    if task:
        tpl_kwargs.update({
            "tests": task.tests
        })

    # conditional render for teacher and student
    if message_launch.check_teacher_access():
        return render_template("teacher.html", **tpl_kwargs)

    return render_template("student.html", **tpl_kwargs)


# This endpoint is used to put mark on the task in the LMS.
@app.route("/api/score/<launch_id>/<earned_score>", methods=["POST"])
def score(launch_id, earned_score):
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf,
                                                   launch_data_storage=launch_data_storage)

    resource_link_id = message_launch.get_launch_data() \
        .get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("id")

    if not message_launch.has_ags():
        raise Forbidden("Don't have grades!")

    sub = message_launch.get_launch_data().get("sub")
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    earned_score = int(earned_score)

    grades = message_launch.get_ags()
    sc = Grade()
    sc.set_score_given(earned_score) \
        .set_score_maximum(100) \
        .set_timestamp(timestamp) \
        .set_activity_progress("Completed") \
        .set_grading_progress("FullyGraded") \
        .set_user_id(sub)

    sc_line_item = LineItem()
    sc_line_item.set_tag("score") \
        .set_score_maximum(100) \
        .set_label("Score")
    if resource_link_id:
        sc_line_item.set_resource_id(resource_link_id)

    result = grades.put_grade(sc, sc_line_item)

    return jsonify({"success": True, "result": result.get("body")})


# Returns scores for the task from the LMS. Currently unused, but can be used for contest spirit
@app.route("/api/scoreboard/<launch_id>/", methods=["GET", "POST"])
def scoreboard(launch_id):
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch.from_cache(launch_id, flask_request, tool_conf,
                                                   launch_data_storage=launch_data_storage)

    resource_link_id = message_launch.get_launch_data() \
        .get("https://purl.imsglobal.org/spec/lti/claim/resource_link", {}).get("id")

    if not message_launch.has_nrps():
        raise Forbidden("Don't have names and roles!")

    if not message_launch.has_ags():
        raise Forbidden("Don't have grades!")

    ags = message_launch.get_ags()

    if ags.can_create_lineitem():
        score_line_item = LineItem()
        score_line_item.set_tag("score") \
            .set_score_maximum(100) \
            .set_label("Score")
        if resource_link_id:
            score_line_item.set_resource_id(resource_link_id)

        score_line_item = ags.find_or_create_lineitem(score_line_item)
        scores = ags.get_grades(score_line_item)

        time_line_item = LineItem()
        time_line_item.set_tag("time") \
            .set_score_maximum(999) \
            .set_label("Time Taken")
        if resource_link_id:
            time_line_item.set_resource_id(resource_link_id)

        time_line_item = ags.find_or_create_lineitem(time_line_item)
        times = ags.get_grades(time_line_item)
    else:
        scores = ags.get_grades()
        times = None

    members = message_launch.get_nrps().get_members()
    scoreboard_result = []

    for sc in scores:
        result = {"score": sc["resultScore"]}
        for tm in times:
            if tm["userId"] == sc["userId"]:
                result["time"] = tm["resultScore"]
                break
        for member in members:
            if member["user_id"] == sc["userId"]:
                result["name"] = member.get("name", "Unknown")
                break
        scoreboard_result.append(result)

    return jsonify(scoreboard_result)


# endpoint that used to create test entity
@app.route('/tests', methods=['POST'])
def create_tests():
    form = request.form
    task_id = form['task_id']
    media_root = app.config['MEDIA_ROOT']
    task_dir = os.path.join(media_root, str(task_id))

    # cleanup previous task
    # It has 1 to 1 relation between LMS task, So much easier to remove previous data, than update current
    db.session.query(Task).filter(Task.id == task_id).delete()
    db.session.query(Test).filter(Test.task_id == task_id).delete()

    task = Task(id=form['task_id'], description=form['description'])
    db.session.add(task)
    # if task already has executable tests - cleanup it
    if not os.path.exists(task_dir):
        os.mkdir(task_dir)
    else:
        # recreate directory
        shutil.rmtree(task_dir)
        os.mkdir(task_dir)

    # iterate over files and store it into database
    for tf in request.files:
        f = request.files[tf]
        filename = secure_filename(f.filename)
        idx = int(tf.split('-')[2])
        db.session.add(Test(description=form[f'test-description-{idx}'], task_id=task.id, file_name=filename))
        f.save(os.path.join(task_dir, filename))

    db.session.commit()
    return jsonify({
        'message': 'ok'
    }), 201


clients: dict[str, Server] = {}
servers: dict[str, Server] = {}


class Event(t.TypedDict):
    event: str
    args: list


# endpoint to run tests for specific student. (student is determined via email)
@app.route("/tests/run/<email>", methods=["POST"])
def run_tests(email):
    global servers

    # if for current student no virtual machine running - return 400 error
    if email not in servers:
        return jsonify({
            "message": "server is offline"
        }), 400

    # send to student`s virtual machine event, to run test
    send_server(email, request.data)
    # wait for response
    data = json.loads(receive_server(email))
    # send event to the student via websocket
    send_client(email, {"event": "test_result", "args": data})

    # return json response
    return jsonify(data)


# send event to the student`s virtual machine via websocket
def send_server(email: str, data: bytes):
    # if there is no email (or student`s machine connection) in the cache - nothing to do here
    if email not in servers:
        return

    try:
        servers[email].send(data)
    except ConnectionClosed:
        print(f"server connection with {email} closed.")
        # if virtual machine is disconnected - remove dead connection from the cache
        if email in servers:
            del servers[email]
        return


# receive will wait for the first message from the server received and return it in the byte representation
def receive_server(email: str) -> bytes:
    if email not in servers:
        return b""

    try:
        return servers[email].receive()
    except ConnectionClosed:
        print(f"server connection with {email} closed.")
        if email in servers:
            del servers[email]


# same logic as for server, but for client (or web interface for now)
def send_client(email: str, event: Event):
    if email not in clients:
        return

    clients[email].send(json.dumps(event))


# endpoint that used by student`s virtual machine to connect to the server, and receive events.
@sock.route("/ws/server/<email>")
def server_sock(ws: Server, email: str):
    global servers

    servers[email] = ws
    send_client(email, {"event": "connected", "args": []})

    while True:
        try:
            ws.send('{"message": "ping"}')
            time.sleep(ws.ping_interval)  # Crutch to keep alive connection and not receive messages
        except ConnectionClosed:
            print(f"server connection with {email} closed.")
            if email in servers:
                del servers[email]
            return


# endpoint that used by client (web interface for now), to connect to the backend via websocket, and receive any update-events
# in realtime
@sock.route("/ws/client/<email>")
def client_sock(ws: Server, email: str):
    global clients

    clients[email] = ws

    if email in servers:
        send_client(email, {"event": "connected", "args": []})

    while True:
        try:
            ws.receive()
        except ConnectionClosed:
            print(f"client connection with {email} closed.")
            if email in clients:
                del clients[email]
            return



# this endpoint is used by studen`s virtual machine to download test`s executable file
@app.route("/tests/download/<task_id>/<filename>", methods=["GET"])
def download_test(task_id, filename):
    return send_file(os.path.join(app.config['MEDIA_ROOT'], task_id, filename))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
