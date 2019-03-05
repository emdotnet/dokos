# coding=utf-8

from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		# Modules
		{
			"module_name": "Getting Started",
			"category": "Modules",
			"label": _("Getting Started"),
			"color": "#1abc9c",
			"icon": "fa fa-check-square-o",
			"type": "module",
			"disable_after_onboard": 1,
			"description": _("Dive into the basics for your organisation's needs."),
			"onboard_present": 1
		},
		{
			"module_name": "Accounting",
			"category": "Modules",
			"label": _("Accounting"),
			"color": "#3498db",
			"icon": "octicon octicon-repo",
			"type": "module",
			"description": "Accounts, billing, payments, cost center and budgeting."
		},
		{
			"module_name": "Selling",
			"category": "Modules",
			"label": _("Selling"),
			"color": "#1abc9c",
			"icon": "octicon octicon-tag",
			"type": "module",
			"description": "All things Sales, Customer and Products."
		},
		{
			"module_name": "Buying",
			"category": "Modules",
			"label": _("Buying"),
			"color": "#c0392b",
			"icon": "octicon octicon-briefcase",
			"type": "module",
			"description": "Purchasing, Suppliers and Products."
		},
		{
			"module_name": "Stock",
			"category": "Modules",
			"label": _("Stock"),
			"color": "#f39c12",
			"icon": "octicon octicon-package",
			"type": "module",
			"description": "Stock transactions, reports, serial numbers and batches."
		},
		{
			"module_name": "Assets",
			"category": "Modules",
			"label": _("Assets"),
			"color": "#4286f4",
			"icon": "octicon octicon-database",
			"type": "module",
			"description": "Asset movement, maintainance and tools."
		},
		{
			"module_name": "Projects",
			"category": "Modules",
			"label": _("Projects"),
			"color": "#8e44ad",
			"icon": "octicon octicon-rocket",
			"type": "module",
			"description": "Updates, Timesheets and Activities."
		},
		{
			"module_name": "CRM",
			"category": "Modules",
			"label": _("CRM"),
			"color": "#EF4DB6",
			"icon": "octicon octicon-broadcast",
			"type": "module",
			"description": "Everything in your sales pipeline, from Leads and Opportunities to Customers."
		},
		{
			"module_name": "Help Desk",
			"category": "Modules",
			"label": _("Help Desk"),
			"color": "#1abc9c",
			"icon": "fa fa-check-square-o",
			"type": "module",
			"description": "User interactions, support issues and knowledge base."
		},
		{
			"module_name": "HR",
			"category": "Modules",
			"label": _("Human Resources"),
			"color": "#2ecc71",
			"icon": "octicon octicon-organization",
			"type": "module",
			"description": "Employee Lifecycle, Payroll, Shifts and Leaves."
		},
		{
			"module_name": "Quality Management",
			"category": "Modules",
			"label": _("Quality"),
			"color": "#1abc9c",
			"icon": "fa fa-check-square-o",
			"type": "module",
			"description": "Quality goals, procedures, reviews and action."
		},


		# Category: "Domains"
		{
			"module_name": "Manufacturing",
			"category": "Domains",
			"label": _("Manufacturing"),
			"color": "#7f8c8d",
			"icon": "octicon octicon-tools",
			"type": "module",
			"description": "Streamline your production with BOMS, Work Orders and Timesheets."
		},
		{
			"module_name": "Retail",
			"category": "Domains",
			"label": _("Retail"),
			"color": "#7f8c8d",
			"icon": "octicon octicon-credit-card",
			"type": "module",
			"description": "Point of Sale, Cashier Closing and Loyalty Programs."
		},

		{
			"module_name": "Help",
			"category": "Administration",
			"label": _("Help"),
			"color": "#FF888B",
			"icon": "octicon octicon-device-camera-video",
			"type": "module",
			"is_help": True,
			"description": "Explore Help Articles and Videos."
		},
		{
			"module_name": "Settings",
			"category": "Administration",
			"label": _("Settings"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"description": "Global settings for all modules in ERPNext, with Email Digest and SMS."
		},
	]
