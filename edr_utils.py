import requests
import json
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.WARN,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_win_edr_config(cid):
    return {
        "src_exe": "/ansible/downloads/crowdstrike_falcon_installer.exe",
        "customer_id": cid
    }


def get_linux_edr_config(client_id, client_secret, sentinel_token, sentinel_api_key, account_id):
    result = install_sentinel_one(
        client_id,
        client_secret,
        sentinel_token,
        sentinel_api_key,
        account_id,
    )
    return result


def install_sentinel_one(client_id: str, client_secret: str, sentinel_api_token: str, sentinel_api_key: str,
                         account_id: str) -> dict:
    """Main function to get SentinelOne installation tokens"""
    try:
        # Get CloudDNA access token
        access_token = get_clouddna_token(client_id, client_secret)

        # Get service ID
        print(f"ACC TOK {access_token} {account_id}")
        service_id = get_service_id(access_token, account_id)

        # Get SentinelOne site token
        print(f"SID {service_id}")
        site_token = get_site_token(sentinel_api_token, service_id)

        return {
            'service_id': service_id,
            'site_token': site_token,
            'api_key': sentinel_api_key
        }

    except Exception as e:
        logger.error(f"Failed to complete SentinelOne installation process: {str(e)}")
        raise


def get_clouddna_token(client_id: str, client_secret: str) -> str:
    """Get access token from CloudDNA API"""
    try:
        url = "https://api.v3.clouddna.autodesk.com/oauth2/app/token"
        data = {
            "client_id": client_id,
            "client_secret": client_secret
        }
        headers = {'Content-type': 'application/json'}

        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()

        access_token = response.json()['access_token']
        logger.info("Successfully obtained CloudDNA access token")
        return access_token

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get CloudDNA access token: {str(e)}")
        raise


def get_service_id(access_token: str, account_id: str) -> str:
    """Get ServiceID for the specified AWS account"""
    try:
        api_endpoint = "https://api.v3.clouddna.autodesk.com/graphql"
        transport = RequestsHTTPTransport(
            url=api_endpoint,
            headers={'Authorization': f'Bearer {access_token}'}
        )

        client = Client(transport=transport, fetch_schema_from_transport=True)

        query = gql("""
            query Query($accountId: ID) {
                account(id: $accountId) {
                    services {
                        serviceId
                    }
                }
            }
        """)

        variables = {'accountId': account_id}
        result = client.execute(query, variable_values=variables)
        print(f" res {result} ")

        if not result.get('account', {}).get('services'):
            raise ValueError(f"No services found for account {account_id}")

        service_id = result['account']['services'][0]['serviceId']
        logger.info(f"Retrieved service ID: {service_id}")
        return service_id

    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"Failed to get service ID: {str(e)}")
        raise


def get_site_token(sentinel_api_token: str, service_id: str) -> str:
    """Get SentinelOne site token using service ID"""
    try:
        url = "https://autodesk.sentinelone.net/web/api/v2.1/sites"
        params = {
            'name': service_id,
            'state': 'active'
        }
        headers = {'Authorization': f'ApiToken {sentinel_api_token}'}

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()

        data = response.json()
        if not data.get('data', {}).get('sites'):
            raise ValueError(f"No active site found for service ID {service_id}")

        site_token = data['data']['sites'][0]['registrationToken']
        logger.info("Successfully retrieved SentinelOne site token")
        return site_token

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get site token: {str(e)}")
        raise


    except Exception as e:
        logger.error(f"Failed to complete SentinelOne installation process: {str(e)}")
        raise
