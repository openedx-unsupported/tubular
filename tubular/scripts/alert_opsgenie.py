from tubular.opsgenie_api import OpsGenieAPI

def alert_opsgenie(auth_token, message, description):
	opsgenie = OpsGenieAPI(auth_token)

	opsgenie.alert_opsgenie(message, description)
