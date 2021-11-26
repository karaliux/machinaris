import json
import os
import re
import time
import traceback

from flask import request, make_response, abort
from flask.views import MethodView

from common.config import globals

from api import app
from api.extensions.api import Blueprint

from api.commands import chia_cli, plotman_cli

blp = Blueprint(
    'Analysis',
    __name__,
    url_prefix='/analysis',
    description="Analysis to perform"
)

@blp.route('/')
class Analysis(MethodView):

    def post(self):
        try:
            body = json.loads(request.data)
            service = body['service']
            action = body['action']
        except:
            abort("Invalid analysis request without service.", 400)
        if service == "plotting" and action == "analyze":
            analysis = plotman_cli.analyze(body['plot_file'])
            if analysis:
                response = make_response(analysis, 200)
                response.mimetype = "plain/text"
                return response
            else: # No such plot file log found on this plotter
                return make_response("Sorry, not plotting job log found. Perhaps plot was made elsewhere?", 404)
        elif service == "farming" and action == "check":
            check = chia_cli.plot_check(globals.enabled_blockchains()[0], body['plot_file'])
            if check: 
                response = make_response(check, 200)
                response.mimetype = "plain/text"
                return response
            else: # No such plot file log found on this plotter
                return make_response("Sorry, not such plot_file found. Perhaps plot on another worker?", 404)
        else:
            abort("Unknown service provided: {0}".format(service))
