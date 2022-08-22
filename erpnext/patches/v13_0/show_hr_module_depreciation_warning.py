import click
import frappe


def execute():
	if "hrms" in frappe.get_installed_apps():
		return

	click.secho(
		"HR and Payroll modules have been moved to a separate app"
		" and will be removed from Dokos in Version 3."
		" Please install the HRMS app when upgrading to Version 3"
		" to continue using the HR and Payroll modules:\n"
		"https://gitlab.com/dokos/hrms",
		fg="yellow",
	)
