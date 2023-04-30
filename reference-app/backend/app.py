from urllib import response
from flask import Flask, render_template, request, jsonify

import pymongo
from flask_pymongo import PyMongo

from flask_cors import CORS
from jaeger_client import Config
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter import jaeger
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics


def init_tracer():
    config = Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name="backend-service",
        validate=True
    )
    return config.initialize_tracer()


jaeger_tracer = init_tracer()

app = Flask(__name__)

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
CORS(app)
metrics = GunicornInternalPrometheusMetrics(app, group_by='endpoint')
metrics.info('backend_service_info', 'Backend Service info', version='1.0.0')

app.config["MONGO_DBNAME"] = "example-mongodb"
app.config[
    "MONGO_URI"
] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

mongo = PyMongo(app)

@app.route('/')
def homepage():
    with jaeger_tracer.start_span('hello world') as span:
        msg = "Hello World"
    return jsonify(response=msg)


@app.route("/api")
def my_api():
   with jaeger_tracer.start_span('api') as span:
        answer = "something"
        span.set_tag('message', answer)
        return jsonify(repsonse=answer)


@app.route("/star", methods=["POST"])
def add_star():
    with jaeger_tracer.start_span('add-star') as span:
        star = mongo.db.stars
        name = request.json["name"]
        distance = request.json["distance"]
        star_id = star.insert({"name": name, "distance": distance})
        new_star = star.find_one({"_id": star_id})
        output = {"name": new_star["name"], "distance": new_star["distance"]}
        return jsonify({"result": output})


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/403")
def status_code_403():
    status_code = 403
    raise InvalidUsage("Raising status code: {}".format(status_code), status_code=status_code)


@app.route("/404")
def status_code_404():
    status_code = 404
    raise InvalidUsage("Raising status code: {}".format(status_code), status_code=status_code)


@app.route("/500")
def status_code_500():
    status_code = 500
    raise InvalidUsage("Raising status code: {}".format(status_code), status_code=status_code)


@app.route("/503")
def status_code_503():
    status_code = 503
    raise InvalidUsage("Raising status code: {}".format(status_code), status_code=status_code)

if __name__ == "__main__":
    app.run()
