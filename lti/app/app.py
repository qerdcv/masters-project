import datetime
import os
import json
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


def get_lti_config_path():
    return os.path.join(app.root_path, "..", "configs", "lti.json")


def get_launch_data_storage():
    return FlaskCacheDataStorage(cache)


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


@app.route("/jwks/", methods=["GET"])
def get_jwks():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    return jsonify(tool_conf.get_jwks())


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


@app.route("/", methods=["POST"])
def launch():
    tool_conf = ToolConfJsonFile(get_lti_config_path())
    flask_request = FlaskRequest()
    launch_data_storage = get_launch_data_storage()
    message_launch = FlaskMessageLaunch(flask_request, tool_conf, launch_data_storage=launch_data_storage)
    message_launch_data = message_launch.get_launch_data()

    tpl_kwargs = {
        "page_title": PAGE_TITLE,
        "is_deep_link_launch": message_launch.is_deep_link_launch(),
        "launch_data": message_launch.get_launch_data(),
        "launch_id": message_launch.get_launch_id(),
        "email": message_launch_data.get("email", ""),
        "task_id": message_launch_data["https://purl.imsglobal.org/spec/lti/claim/resource_link"]["id"],
    }

    if message_launch.check_teacher_access():
        return render_template("teacher.html", **tpl_kwargs)

    tpl_kwargs.update({
        "tests": [
            {
                "name": "check_docker",
                "description": "Check docker installation",
            },
            {
                "name": "failed",
                "description": "Test should be failed.",
            },
        ]
    })

    return render_template("student.html", **tpl_kwargs)


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


@app.route('/tests', methods=['POST'])
def create_tests():
    form = request.form
    media_root = app.config['MEDIA_ROOT']
    task_dir = os.path.join(media_root, str(form['task_id']))
    task = Task(id=form['task_id'], description=form['description'])
    db.session.add(task)
    if not os.path.exists(task_dir):
        os.mkdir(task_dir)

    for idx, tf in enumerate(request.files):
        f = request.files[tf]
        filename = secure_filename(f.filename)
        f.save(os.path.join(task_dir, filename))

        db.session.add(Test(description=form[f'test-description-{idx}'], task_id=task.id, file_name=filename))

    db.session.commit()
    return jsonify({
        'message': 'ok'
    }), 201


clients: dict[str, Server] = {}
servers: dict[str, Server] = {}


class Event(t.TypedDict):
    event: str
    args: list

@app.route("/tests/run/<email>", methods=["POST"])
def run_tests(email):
    global servers

    if email not in servers:
        return jsonify({
            "message": "server is offline"
        }), 400

    servers[email].send(request.data)

    return jsonify({
        "message": "ok"
    })


def send_client(email: str, event: Event):
    if email not in clients:
        return

    clients[email].send(json.dumps(event))


@sock.route("/ws/server/<email>")
def server_sock(ws: Server, email: str):
    global servers

    servers[email] = ws
    send_client(email, {"event": "connected", "args": []})

    while True:
        try:
            send_client(email, {"event": "test_result", "args": json.loads(ws.receive())})
        except ConnectionClosed:
            del servers[email]
            send_client(email, {"event": "disconnected", "args": []})
            print(f"server connection with {email} closed.")
            return


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
            del clients[email]
            return


@app.route("/tests/download/<filename>", methods=["GET"])
def download_test(filename):
    return send_file(os.path.join(app.root_path, "tests", filename))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9001)
