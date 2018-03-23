'''Application error handlers.'''
from flask import Blueprint, jsonify

import traceback

errors = Blueprint('errors', __name__)

@errors.app_errorhandler(Exception)
def handle_unexpected_error(error):
    print(traceback.print_exc())

    status_code = 500
    success = False
    response = {
        'success': success,
        'error': {
            'type': 'UnexpectedException',
            'message': str(error)
        }
    }

    return jsonify(response), status_code