import json
from function import called_from_ymq_trigger, ymq_handler, send_to_slack, send_to_ymq_queue, make_response

def http_handler(event, context):
    # --- Comment this ---
    send_to_slack(message=json.loads(event['body']))

    # --- Uncomment this ---
    # queue_url = <put your queue url here>
    # send_to_ymq_queue(queue_url, event['body'])

    return make_response()

def handler(event, context):
    if called_from_ymq_trigger(event, context):
        return ymq_handler(event, context)
    else:
        return http_handler(event, context)

