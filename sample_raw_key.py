import google.auth
from google.cloud import kms_v1
from google.api_core.client_options import ClientOptions

credentials, _ = google.auth.default()

cert = b"""<fill in>"""

key = b"""<fill in>"""

project = "sijunliu-dca-test"

def my_cert_source():
    return cert, key

def run_sample(client_cert_source):
    options = ClientOptions(client_cert_source=client_cert_source)

    client = kms_v1.KeyManagementServiceClient(client_options=options)
    parent = f"projects/{project}/locations/global"
    res = client.list_key_rings(request={"parent": parent})
    print(res)


run_sample(my_cert_source)