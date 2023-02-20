import cfnresponse
import json
import logging
import random
import string

logger = logging.getLogger(__name__)


def generate_random_string(length):
    return "".join(
        random.choice(string.ascii_uppercase + string.digits)  # nosec B311
        for _ in range(length)
    )


def handler(event, context):
    props = event.get("ResourceProperties", {})
    logger.setLevel(props.get("LogLevel", logging.INFO))

    logger.debug(json.dumps(event))

    random_string = ""
    physical_resource_id = event.get("PhysicalResourceId", None)

    if event["RequestType"] == "Create":
        length = int(event.get("ResourceProperties", {}).get("Length", 64))
        random_string = generate_random_string(length)
        physical_resource_id = random_string

    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {"Value": random_string},
        physical_resource_id,
    )
