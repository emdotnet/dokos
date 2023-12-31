import click
import frappe


def execute():
	click.secho(
		"Shopify Integration is moved to a separate app and will be removed from Dokos in version 3.\n"
		"Please install the app to continue using the integration: https://github.com/frappe/ecommerce_integrations",
		fg="yellow",
	)
