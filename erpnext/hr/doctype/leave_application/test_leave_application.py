# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import unittest

import frappe
from frappe.permissions import clear_user_permissions_for_doctype
from frappe.utils import (
	add_days,
	add_months,
	get_first_day,
	get_last_day,
	get_year_ending,
	get_year_start,
	getdate,
	nowdate,
)

from erpnext.hr.doctype.employee.test_employee import make_employee
from erpnext.hr.doctype.leave_allocation.test_leave_allocation import create_leave_allocation
from erpnext.hr.doctype.leave_application.leave_application import (
	LeaveDayBlockedError,
	NotAnOptionalHoliday,
	OverlapError,
	get_leave_balance_on,
)
from erpnext.hr.doctype.leave_policy_assignment.leave_policy_assignment import (
	create_assignment_for_multiple_employees,
)
from erpnext.hr.doctype.leave_type.test_leave_type import create_leave_type
from erpnext.payroll.doctype.salary_slip.test_salary_slip import (
	make_holiday_list,
	make_leave_application,
)

test_dependencies = ["Leave Allocation", "Leave Block List", "Employee"]

_test_records = [
	{
		"company": "_Test Company",
		"doctype": "Leave Application",
		"employee": "_T-Employee-00001",
		"from_date": "2013-05-01",
		"description": "_Test Reason",
		"leave_type": "_Test Leave Type",
		"posting_date": "2013-01-02",
		"to_date": "2013-05-05"
	},
	{
		"company": "_Test Company",
		"doctype": "Leave Application",
		"employee": "_T-Employee-00002",
		"from_date": "2013-05-01",
		"description": "_Test Reason",
		"leave_type": "_Test Leave Type",
		"posting_date": "2013-01-02",
		"to_date": "2013-05-05"
	},
	{
		"company": "_Test Company",
		"doctype": "Leave Application",
		"employee": "_T-Employee-00001",
		"from_date": "2013-01-15",
		"description": "_Test Reason",
		"leave_type": "_Test Leave Type LWP",
		"posting_date": "2013-01-02",
		"to_date": "2013-01-15"
	}
]


class TestLeaveApplication(unittest.TestCase):
	def setUp(self):
		for dt in ["Leave Application", "Leave Allocation", "Salary Slip", "Leave Ledger Entry"]:
			frappe.db.sql("DELETE FROM `tab%s`" % dt) #nosec

		frappe.set_user("Administrator")
		set_leave_approver()

		frappe.db.sql("delete from tabAttendance where employee='_T-Employee-00001'")

	def tearDown(self):
		frappe.db.rollback()

	def _clear_roles(self):
		frappe.db.sql("""delete from `tabHas Role` where parent in
			("test@example.com", "test1@example.com", "test2@example.com")""")

	def _clear_applications(self):
		frappe.db.sql("""delete from `tabLeave Application`""")

	def get_application(self, doc):
		application = frappe.copy_doc(doc)
		application.from_date = "2013-01-01"
		application.to_date = "2013-01-05"
		return application

	def test_overwrite_attendance(self):
		'''check attendance is automatically created on leave approval'''
		make_allocation_record()
		application = self.get_application(_test_records[0])
		application.status = 'Approved'
		application.from_date = '2018-01-01'
		application.to_date = '2018-01-03'
		application.insert()
		application.submit()

		attendance = frappe.get_all('Attendance', ['name', 'status', 'attendance_date'],
			dict(attendance_date=('between', ['2018-01-01', '2018-01-03']), docstatus=("!=", 2)))

		# attendance created for all 3 days
		self.assertEqual(len(attendance), 3)

		# all on leave
		self.assertTrue(all([d.status == 'On Leave' for d in attendance]))

		# dates
		dates = [d.attendance_date for d in attendance]
		for d in ('2018-01-01', '2018-01-02', '2018-01-03'):
			self.assertTrue(getdate(d) in dates)

	def test_attendance_for_include_holidays(self):
		# Case 1: leave type with 'Include holidays within leaves as leaves' enabled
		frappe.delete_doc_if_exists("Leave Type", "Test Include Holidays", force=1)
		leave_type = frappe.get_doc(dict(
			leave_type_name="Test Include Holidays",
			doctype="Leave Type",
			include_holiday=True
		)).insert()

		date = getdate()
		make_allocation_record(leave_type=leave_type.name, from_date=get_year_start(date), to_date=get_year_ending(date))

		holiday_list = make_holiday_list()
		employee = get_employee()
		original_holiday_list = employee.holiday_list
		frappe.db.set_value("Employee", employee.name, "holiday_list", holiday_list)

		first_sunday = get_first_sunday(holiday_list)

		leave_application = make_leave_application(employee.name, first_sunday, add_days(first_sunday, 3), leave_type.name)
		leave_application.reload()
		self.assertEqual(leave_application.total_leave_days, 4)
		self.assertEqual(frappe.db.count('Attendance', {'leave_application': leave_application.name}), 4)

		leave_application.cancel()

		frappe.db.set_value("Employee", employee.name, "holiday_list", original_holiday_list)

	def test_attendance_update_for_exclude_holidays(self):
		# Case 2: leave type with 'Include holidays within leaves as leaves' disabled
		frappe.delete_doc_if_exists("Leave Type", "Test Do Not Include Holidays", force=1)
		leave_type = frappe.get_doc(dict(
			leave_type_name="Test Do Not Include Holidays",
			doctype="Leave Type",
			include_holiday=False
		)).insert()

		date = getdate()
		make_allocation_record(leave_type=leave_type.name, from_date=get_year_start(date), to_date=get_year_ending(date))

		holiday_list = make_holiday_list()
		employee = get_employee()
		original_holiday_list = employee.holiday_list
		frappe.db.set_value("Employee", employee.name, "holiday_list", holiday_list)
		first_sunday = get_first_sunday(holiday_list)

		# already marked attendance on a holiday should be deleted in this case
		config = {
			"doctype": "Attendance",
			"employee": employee.name,
			"status": "Present"
		}
		attendance_on_holiday = frappe.get_doc(config)
		attendance_on_holiday.attendance_date = first_sunday
		attendance_on_holiday.flags.ignore_validate = True
		attendance_on_holiday.save()

		# already marked attendance on a non-holiday should be updated
		attendance = frappe.get_doc(config)
		attendance.attendance_date = add_days(first_sunday, 3)
		attendance.flags.ignore_validate = True
		attendance.save()

		leave_application = make_leave_application(employee.name, first_sunday, add_days(first_sunday, 3), leave_type.name, employee.company)
		leave_application.reload()
		# holiday should be excluded while marking attendance
		self.assertEqual(leave_application.total_leave_days, 3)
		self.assertEqual(frappe.db.count("Attendance", {"leave_application": leave_application.name}), 3)

		# attendance on holiday deleted
		self.assertFalse(frappe.db.exists("Attendance", attendance_on_holiday.name))

		# attendance on non-holiday updated
		self.assertEqual(frappe.db.get_value("Attendance", attendance.name, "status"), "On Leave")

		frappe.db.set_value("Employee", employee.name, "holiday_list", original_holiday_list)

	def test_block_list(self):
		self._clear_roles()

		from frappe.utils.user import add_role
		add_role("test@example.com", "HR User")
		clear_user_permissions_for_doctype("Employee")

		frappe.db.set_value("Department", "_Test Department - _TC",
			"leave_block_list", "_Test Leave Block List")

		make_allocation_record()

		application = self.get_application(_test_records[0])
		application.insert()
		application.reload()
		application.status = "Approved"
		self.assertRaises(LeaveDayBlockedError, application.submit)

		frappe.set_user("test@example.com")

		# clear other applications
		frappe.db.sql("delete from `tabLeave Application`")

		application = self.get_application(_test_records[0])
		self.assertTrue(application.insert())

	def test_overlap(self):
		self._clear_roles()
		self._clear_applications()

		from frappe.utils.user import add_role
		add_role("test@example.com", "Employee")
		frappe.set_user("test@example.com")

		make_allocation_record()

		application = self.get_application(_test_records[0])
		application.insert()

		application = self.get_application(_test_records[0])
		self.assertRaises(OverlapError, application.insert)

	def test_overlap_with_half_day_1(self):
		self._clear_roles()
		self._clear_applications()

		from frappe.utils.user import add_role
		add_role("test@example.com", "Employee")
		frappe.set_user("test@example.com")

		make_allocation_record()

		# leave from 1-5, half day on 3rd
		application = self.get_application(_test_records[0])
		application.half_day = 1
		application.half_day_date = "2013-01-03"
		application.insert()

		# Apply again for a half day leave on 3rd
		application = self.get_application(_test_records[0])
		application.from_date = "2013-01-03"
		application.to_date = "2013-01-03"
		application.half_day = 1
		application.half_day_date = "2013-01-03"
		application.insert()

		# Apply again for a half day leave on 3rd
		application = self.get_application(_test_records[0])
		application.from_date = "2013-01-03"
		application.to_date = "2013-01-03"
		application.half_day = 1
		application.half_day_date = "2013-01-03"

		self.assertRaises(OverlapError, application.insert)

	def test_overlap_with_half_day_2(self):
		self._clear_roles()
		self._clear_applications()

		from frappe.utils.user import add_role
		add_role("test@example.com", "Employee")

		frappe.set_user("test@example.com")

		make_allocation_record()

		# leave from 1-5, no half day
		application = self.get_application(_test_records[0])
		application.insert()

		# Apply again for a half day leave on 1st
		application = self.get_application(_test_records[0])
		application.half_day = 1
		application.half_day_date = application.from_date

		self.assertRaises(OverlapError, application.insert)

	def test_overlap_with_half_day_3(self):
		self._clear_roles()
		self._clear_applications()

		from frappe.utils.user import add_role
		add_role("test@example.com", "Employee")

		frappe.set_user("test@example.com")

		make_allocation_record()

		# leave from 1-5, half day on 5th
		application = self.get_application(_test_records[0])
		application.half_day = 1
		application.half_day_date = "2013-01-05"
		application.insert()

		# Apply leave from 4-7, half day on 5th
		application = self.get_application(_test_records[0])
		application.from_date = "2013-01-04"
		application.to_date = "2013-01-07"
		application.half_day = 1
		application.half_day_date = "2013-01-05"

		self.assertRaises(OverlapError, application.insert)

		# Apply leave from 5-7, half day on 5th
		application = self.get_application(_test_records[0])
		application.from_date = "2013-01-05"
		application.to_date = "2013-01-07"
		application.half_day = 1
		application.half_day_date = "2013-01-05"
		application.insert()

	def test_optional_leave(self):
		leave_period = get_leave_period()
		today = nowdate()
		holiday_list = 'Test Holiday List for Optional Holiday'
		employee = get_employee()

		default_holiday_list = make_holiday_list()
		original_holiday_list = employee.holiday_list
		frappe.db.set_value("Employee", employee.name, "holiday_list", default_holiday_list)
		first_sunday = get_first_sunday(default_holiday_list)

		optional_leave_date = add_days(first_sunday, 1)

		if not frappe.db.exists('Holiday List', holiday_list):
			frappe.get_doc(dict(
				doctype = 'Holiday List',
				holiday_list_name = holiday_list,
				from_date = add_months(today, -6),
				to_date = add_months(today, 6),
				holidays = [
					dict(holiday_date = optional_leave_date, description = 'Test')
				]
			)).insert()

		frappe.db.set_value('Leave Period', leave_period.name, 'optional_holiday_list', holiday_list)
		leave_type = 'Test Optional Type'
		if not frappe.db.exists('Leave Type', leave_type):
			frappe.get_doc(dict(
				leave_type_name = leave_type,
				doctype = 'Leave Type',
				is_optional_leave = 1
			)).insert()

		allocate_leaves(employee, leave_period, leave_type, 10)

		date = add_days(first_sunday, 2)

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			company = '_Test Company',
			description = "_Test Reason",
			leave_type = leave_type,
			from_date = date,
			to_date = date,
		))

		# can only apply on optional holidays
		self.assertRaises(NotAnOptionalHoliday, leave_application.insert)

		leave_application.from_date = optional_leave_date
		leave_application.to_date = optional_leave_date
		leave_application.status = "Approved"
		leave_application.insert()
		leave_application.submit()

		# check leave balance is reduced
		self.assertEqual(get_leave_balance_on(employee.name, leave_type, optional_leave_date), 9)

		frappe.db.set_value("Employee", employee.name, "holiday_list", original_holiday_list)

	def test_leaves_allowed(self):
		employee = get_employee()
		leave_period = get_leave_period()
		frappe.delete_doc_if_exists("Leave Type", "Test Leave Type", force=1)
		leave_type = frappe.get_doc(dict(
			leave_type_name = 'Test Leave Type',
			doctype = 'Leave Type',
			max_leaves_allowed = 5
		)).insert()

		date = add_days(nowdate(), -7)

		allocate_leaves(employee, leave_period, leave_type.name, 5)

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			description = "_Test Reason",
			from_date = date,
			to_date = add_days(date, 2),
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))
		leave_application.submit()

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			description = "_Test Reason",
			from_date = add_days(date, 4),
			to_date = add_days(date, 8),
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))
		self.assertRaises(frappe.ValidationError, leave_application.insert)

	def test_applicable_after(self):
		employee = get_employee()
		leave_period = get_leave_period()
		frappe.delete_doc_if_exists("Leave Type", "Test Leave Type", force=1)
		leave_type = frappe.get_doc(dict(
			leave_type_name = 'Test Leave Type',
			doctype = 'Leave Type',
			applicable_after = 15
		)).insert()
		date = add_days(nowdate(), -7)
		frappe.db.set_value('Employee', employee.name, "date_of_joining", date)
		allocate_leaves(employee, leave_period, leave_type.name, 10)

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			description = "_Test Reason",
			from_date = date,
			to_date = add_days(date, 4),
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))

		self.assertRaises(frappe.ValidationError, leave_application.insert)

		frappe.delete_doc_if_exists("Leave Type", "Test Leave Type 1", force=1)
		leave_type_1 = frappe.get_doc(dict(
			leave_type_name = 'Test Leave Type 1',
			doctype = 'Leave Type'
		)).insert()

		allocate_leaves(employee, leave_period, leave_type_1.name, 10)

		leave_application = frappe.get_doc(dict(
		doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type_1.name,
			description = "_Test Reason",
			from_date = date,
			to_date = add_days(date, 4),
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))

		self.assertTrue(leave_application.insert())
		frappe.db.set_value('Employee', employee.name, "date_of_joining", "2010-01-01")

	def test_max_continuous_leaves(self):
		employee = get_employee()
		leave_period = get_leave_period()
		frappe.delete_doc_if_exists("Leave Type", "Test Leave Type", force=1)
		leave_type = frappe.get_doc(dict(
			leave_type_name = 'Test Leave Type',
			doctype = 'Leave Type',
			max_leaves_allowed = 15,
			max_continuous_days_allowed = 3
		)).insert()

		date = add_days(nowdate(), -7)

		allocate_leaves(employee, leave_period, leave_type.name, 10)

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			description = "_Test Reason",
			from_date = date,
			to_date = add_days(date, 4),
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))

		self.assertRaises(frappe.ValidationError, leave_application.insert)

	def test_leave_balance_near_allocaton_expiry(self):
		employee = get_employee()
		leave_type = create_leave_type(
			leave_type_name="_Test_CF_leave_expiry",
			is_carry_forward=1,
			expire_carry_forwarded_leaves_after_days=90)
		leave_type.submit()

		create_carry_forwarded_allocation(employee, leave_type)

		self.assertEqual(get_leave_balance_on(employee.name, leave_type.name, nowdate(), add_days(nowdate(), 8)), 21)

	def test_earned_leaves_creation(self):

		frappe.db.sql('''delete from `tabLeave Period`''')
		frappe.db.sql('''delete from `tabLeave Policy Assignment`''')
		frappe.db.sql('''delete from `tabLeave Allocation`''')
		frappe.db.sql('''delete from `tabLeave Ledger Entry`''')

		leave_period = get_leave_period()
		employee = get_employee()
		leave_type = 'Test Earned Leave Type'
		frappe.delete_doc_if_exists("Leave Type", 'Test Earned Leave Type', force=1)
		frappe.get_doc(dict(
			leave_type_name = leave_type,
			doctype = 'Leave Type',
			is_earned_leave = 1,
			earned_leave_frequency = 'Monthly',
			rounding = 0.5,
			max_leaves_allowed = 6
		)).insert()

		leave_policy = frappe.get_doc({
			"doctype": "Leave Policy",
			"title": "Test Leave Policy",
			"leave_policy_details": [{"leave_type": leave_type, "annual_allocation": 6}]
		}).insert()

		data = {
			"assignment_based_on": "Leave Period",
			"leave_policy": leave_policy.name,
			"leave_period": leave_period.name
		}

		leave_policy_assignments = create_assignment_for_multiple_employees([employee.name], frappe._dict(data))

		from erpnext.hr.utils import allocate_earned_leaves
		i = 0
		while(i<14):
			allocate_earned_leaves()
			i += 1
		self.assertEqual(get_leave_balance_on(employee.name, leave_type, nowdate()), 6)

		# validate earned leaves creation without maximum leaves
		frappe.db.set_value('Leave Type', leave_type, 'max_leaves_allowed', 0)
		i = 0
		while(i<6):
			allocate_earned_leaves()
			i += 1
		self.assertEqual(get_leave_balance_on(employee.name, leave_type, nowdate()), 9)

	# test to not consider current leave in leave balance while submitting
	def test_current_leave_on_submit(self):
		employee = get_employee()
		leave_type = 'Sick leave'
		allocation = frappe.get_doc(dict(
			doctype = 'Leave Allocation',
			employee = employee.name,
			leave_type = leave_type,
			from_date = '2018-10-01',
			to_date = '2018-10-10',
			new_leaves_allocated = 1
		))
		allocation.insert(ignore_permissions=True)
		allocation.submit()
		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type,
			description = "_Test Reason",
			from_date = '2018-10-02',
			to_date = '2018-10-02',
			company = '_Test Company',
			status = 'Approved',
			leave_approver = 'test@example.com'
		))
		self.assertTrue(leave_application.insert())
		leave_application.submit()
		self.assertEqual(leave_application.docstatus, 1)

	def test_creation_of_leave_ledger_entry_on_submit(self):
		employee = get_employee()

		leave_type = create_leave_type(leave_type_name = 'Test Leave Type 1')
		leave_type.save()

		leave_allocation = create_leave_allocation(employee=employee.name, employee_name=employee.employee_name,
			leave_type=leave_type.name)
		leave_allocation.submit()

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			from_date = add_days(nowdate(), 1),
			to_date = add_days(nowdate(), 4),
			description = "_Test Reason",
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))
		leave_application.submit()
		leave_ledger_entry = frappe.get_all('Leave Ledger Entry', fields='*', filters=dict(transaction_name=leave_application.name))

		self.assertEqual(leave_ledger_entry[0].employee, leave_application.employee)
		self.assertEqual(leave_ledger_entry[0].leave_type, leave_application.leave_type)
		self.assertEqual(leave_ledger_entry[0].leaves, leave_application.total_leave_days * -1)

		# check if leave ledger entry is deleted on cancellation
		leave_application.cancel()
		self.assertFalse(frappe.db.exists("Leave Ledger Entry", {'transaction_name':leave_application.name}))

	def test_ledger_entry_creation_on_intermediate_allocation_expiry(self):
		employee = get_employee()
		leave_type = create_leave_type(
			leave_type_name="_Test_CF_leave_expiry",
			is_carry_forward=1,
			expire_carry_forwarded_leaves_after_days=90)
		leave_type.submit()

		create_carry_forwarded_allocation(employee, leave_type)

		leave_application = frappe.get_doc(dict(
			doctype = 'Leave Application',
			employee = employee.name,
			leave_type = leave_type.name,
			from_date = add_days(nowdate(), -3),
			to_date = add_days(nowdate(), 7),
			description = "_Test Reason",
			company = "_Test Company",
			docstatus = 1,
			status = "Approved"
		))
		leave_application.submit()

		leave_ledger_entry = frappe.get_all('Leave Ledger Entry', '*', filters=dict(transaction_name=leave_application.name))

		self.assertEqual(len(leave_ledger_entry), 2)
		self.assertEqual(leave_ledger_entry[0].employee, leave_application.employee)
		self.assertEqual(leave_ledger_entry[0].leave_type, leave_application.leave_type)
		self.assertEqual(leave_ledger_entry[0].leaves, -9)
		self.assertEqual(leave_ledger_entry[1].leaves, -2)

	def test_leave_application_creation_after_expiry(self):
		# test leave balance for carry forwarded allocation
		employee = get_employee()
		leave_type = create_leave_type(
			leave_type_name="_Test_CF_leave_expiry",
			is_carry_forward=1,
			expire_carry_forwarded_leaves_after_days=90)
		leave_type.submit()

		create_carry_forwarded_allocation(employee, leave_type)

		self.assertEqual(get_leave_balance_on(employee.name, leave_type.name, add_days(nowdate(), -85), add_days(nowdate(), -84)), 0)

	def test_leave_approver_perms(self):
		employee = get_employee()
		user = "test_approver_perm_emp@example.com"
		make_employee(user, "_Test Company")

		# set approver for employee
		employee.reload()
		employee.leave_approver = user
		employee.save()
		self.assertTrue("Leave Approver" in frappe.get_roles(user))

		make_allocation_record(employee.name)

		application = self.get_application(_test_records[0])
		application.from_date = '2018-01-01'
		application.to_date = '2018-01-03'
		application.leave_approver = user
		application.insert()
		self.assertTrue(application.name in frappe.share.get_shared("Leave Application", user))

		# check shared doc revoked
		application.reload()
		application.leave_approver = "test@example.com"
		application.save()
		self.assertTrue(application.name not in frappe.share.get_shared("Leave Application", user))

		application.reload()
		application.leave_approver = user
		application.save()

		frappe.set_user(user)
		application.reload()
		application.status = "Approved"
		application.submit()

		# unset leave approver
		frappe.set_user("Administrator")
		employee.reload()
		employee.leave_approver = ""
		employee.save()


def create_carry_forwarded_allocation(employee, leave_type):
		# initial leave allocation
		leave_allocation = create_leave_allocation(
			leave_type="_Test_CF_leave_expiry",
			employee=employee.name,
			employee_name=employee.employee_name,
			from_date=add_months(nowdate(), -24),
			to_date=add_months(nowdate(), -12),
			carry_forward=0)
		leave_allocation.submit()

		leave_allocation = create_leave_allocation(
			leave_type="_Test_CF_leave_expiry",
			employee=employee.name,
			employee_name=employee.employee_name,
			from_date=add_days(nowdate(), -84),
			to_date=add_days(nowdate(), 100),
			carry_forward=1)
		leave_allocation.submit()

def make_allocation_record(employee=None, leave_type=None, from_date=None, to_date=None):
	allocation = frappe.get_doc({
		"doctype": "Leave Allocation",
		"employee": employee or "_T-Employee-00001",
		"leave_type": leave_type or "_Test Leave Type",
		"from_date": from_date or "2013-01-01",
		"to_date": to_date or "2019-12-31",
		"new_leaves_allocated": 30
	})

	allocation.insert(ignore_permissions=True)
	allocation.submit()

def get_employee():
	return frappe.get_doc("Employee", "_T-Employee-00001")

def set_leave_approver():
	employee = get_employee()
	dept_doc = frappe.get_doc("Department", employee.department)
	dept_doc.append('leave_approvers', {
		'approver': 'test@example.com'
	})
	dept_doc.save(ignore_permissions=True)

def get_leave_period():
	leave_period_name = frappe.db.exists({
		"doctype": "Leave Period",
		"company": "_Test Company"
	})
	if leave_period_name:
		return frappe.get_doc("Leave Period", leave_period_name[0][0])
	else:
		return frappe.get_doc(dict(
				name = 'Test Leave Period',
				doctype = 'Leave Period',
				from_date = add_months(nowdate(), -6),
				to_date = add_months(nowdate(), 6),
				company = "_Test Company",
				is_active = 1
			)).insert()

def allocate_leaves(employee, leave_period, leave_type, new_leaves_allocated, eligible_leaves=0):
	allocate_leave = frappe.get_doc({
		"doctype": "Leave Allocation",
		"__islocal": 1,
		"employee": employee.name,
		"employee_name": employee.employee_name,
		"leave_type": leave_type,
		"from_date": leave_period.from_date,
		"to_date": leave_period.to_date,
		"new_leaves_allocated": new_leaves_allocated,
		"docstatus": 1
	}).insert()

	allocate_leave.submit()


def get_first_sunday(holiday_list, for_date=None):
	date = for_date or getdate()
	month_start_date = get_first_day(date)
	month_end_date = get_last_day(date)
	first_sunday = frappe.db.sql("""
		select holiday_date from `tabHoliday`
		where parent = %s
			and holiday_date between %s and %s
		order by holiday_date
	""", (holiday_list, month_start_date, month_end_date))[0][0]

	return first_sunday
