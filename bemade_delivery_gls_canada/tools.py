import requests
import logging
import json
from requests.auth import HTTPBasicAuth
from models.gls_canada_credentials import GLSCanadaAccount
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def api_call(account: GLSCanadaAccount, endpoint: str, method: str, request_data: dict,
             headers: dict = {"Content-Type": "application/json"},
             ) -> requests.Response:
    """
    Make a call to the GLS Canada API using the credentials set on the current
    company_id


    :param endpoint: The endpoint to use, such as "/pickup/list"
    :param method:  The request method to use, typically "GET" or "POST"
    :param headers: Request headers
    :param request_data:
    :return: A list of dicts matching the GLS Canada API response specifications
    """
    request_data = json.dumps(request_data)
    try:
        api_url = "%s%s" % (
            account.account_credentials.url, endpoint)
        _logger.info("Sending GLS Canada request %s" % request_data)
        username = account.account_credentials.username
        password = account.account_credentials.password
        if method == "GET":
            response_body = requests.get(url=api_url, params=request_data,
                                         headers=headers,
                                         auth=HTTPBasicAuth(username, password))
        elif method == "DELETE":
            response_body = requests.delete(url=api_url, params=request_data,
                                            headers=headers,
                                            auth=HTTPBasicAuth(username, password))
        else:
            response_body = requests.request(method=method, url=api_url,
                                             data=request_data, headers=headers,
                                             auth=HTTPBasicAuth(username, password))
        _logger.info(f"GLS Canada Response Status Code: {response_body.status_code}")
        _logger.info("GLS Canada API Response: %s" % response_body.content)
        return response_body
    except Exception as e:
        raise ValidationError(e)
