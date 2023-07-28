async function archive_this_address(name) {
	await frappe.xcall("frappe.client.set_value", {
		doctype: "Address",
		name: name,
		fieldname: "disabled",
		value: 1,
	});
	window.location.href = "/{{ route }}/list";
}