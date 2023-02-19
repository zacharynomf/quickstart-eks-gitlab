from __future__ import print_function
import base64
import hashlib
import hmac
import json
import logging
from crhelper import CfnResource

# Values that are required to calculate the signature. These values should
# never change.
DATE = "11111111"
SERVICE = "ses"
MESSAGE = "SendRawEmail"
TERMINAL = "aws4_request"
VERSION = 0x04

logger = logging.getLogger(__name__)
# Initialise the helper, all inputs are optional, this example shows the defaults
helper = CfnResource(
    json_logging=False, log_level="DEBUG", boto_level="CRITICAL", sleep_on_delete=120
)


@helper.create
@helper.update
def create(event, _):
    logger.info("Got Create")
    region = event["ResourceProperties"]["Region"]
    secret = event["ResourceProperties"]["Secret"]

    logger.info(f"Calculating password for{region}")
    smtp_password = calculateKey(secret, region)
    helper.Data.update({"Password": smtp_password})


@helper.delete
def delete(_event, _):
    logger.info("Got Delete")


def handler(event, context):
    props = event.get("ResourceProperties", {})
    logger.setLevel(props.get("LogLevel", logging.INFO))

    logger.debug(json.dumps(event))

    helper(event, context)


def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


# https://docs.aws.amazon.com/ses/latest/DeveloperGuide/smtp-credentials.html#smtp-credentials-convert
def calculateKey(secretAccessKey, region):
    signature = sign(("AWS4" + secretAccessKey).encode("utf-8"), DATE)
    signature = sign(signature, region)
    signature = sign(signature, SERVICE)
    signature = sign(signature, TERMINAL)
    signature = sign(signature, MESSAGE)
    signatureAndVersion = bytes([VERSION]) + signature
    smtpPassword = base64.b64encode(signatureAndVersion)

    return smtpPassword.decode("utf-8")
