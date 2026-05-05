app_name = "triplen_connection"
app_title = "Triplen Connection"
app_publisher = "David Gitau"
app_description = "Triple N Caregivers Connection. A professional staffing agency dedicated to delivering dependable and qualified caregiving personnel."
app_email = "muruthigitau@gmail.com"
app_license = "agpl-3.0"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "triplen_connection",
# 		"logo": "/assets/triplen_connection/logo.png",
# 		"title": "Triplen Connection",
# 		"route": "/triplen_connection",
# 		"has_permission": "triplen_connection.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/triplen_connection/css/triplen_connection.css"
# app_include_js = "/assets/triplen_connection/js/triplen_connection.js"

# include js, css files in header of web template
# web_include_css = "/assets/triplen_connection/css/triplen_connection.css"
# web_include_js = "/assets/triplen_connection/js/triplen_connection.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "triplen_connection/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "triplen_connection/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "triplen_connection.utils.jinja_methods",
# 	"filters": "triplen_connection.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "triplen_connection.install.before_install"
# after_install = "triplen_connection.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "triplen_connection.uninstall.before_uninstall"
# after_uninstall = "triplen_connection.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "triplen_connection.utils.before_app_install"
# after_app_install = "triplen_connection.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "triplen_connection.utils.before_app_uninstall"
# after_app_uninstall = "triplen_connection.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "triplen_connection.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"triplen_connection.tasks.all"
# 	],
# 	"daily": [
# 		"triplen_connection.tasks.daily"
# 	],
# 	"hourly": [
# 		"triplen_connection.tasks.hourly"
# 	],
# 	"weekly": [
# 		"triplen_connection.tasks.weekly"
# 	],
# 	"monthly": [
# 		"triplen_connection.tasks.monthly"
# 	],
# }
scheduler_events = {
	"daily": [
		"triplen_connection.triplen_connection.doctype.caregiver_membership.caregiver_membership.set_expired_memberships"
	]
}

# Testing
# -------

# before_tests = "triplen_connection.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "triplen_connection.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "triplen_connection.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["triplen_connection.utils.before_request"]
# after_request = ["triplen_connection.utils.after_request"]

# Job Events
# ----------
# before_job = ["triplen_connection.utils.before_job"]
# after_job = ["triplen_connection.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"triplen_connection.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
