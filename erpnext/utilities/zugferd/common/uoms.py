import frappe

from .uom_map import fallback_code
from .uom_map import uom_map as _uom_map


def _normalize(uom_name: str):
	return uom_name.lower().replace("/", "per").replace("-", " ")


# Add custom UOMs here
uom_map: dict[str, str] = {
	"unit": _uom_map["piece"],
	_normalize(frappe._("Unit")): _uom_map["piece"],
	"percentage": _uom_map["percent"],
	**_uom_map,
}

uom_map_lower = {_normalize(k): v for k, v in uom_map.items()}


def _lookup(uom_name: str):
	yield uom_map.get(uom_name)
	yield uom_map_lower.get(_normalize(uom_name))
	yield uom_map_lower.get(_normalize(frappe._(uom_name)))


def get_unece_rec20_code_for_uom(uom_name: str):
	if not isinstance(uom_name, str):
		raise TypeError("uom_name must be of type string")

	for code in _lookup(uom_name):
		if code:
			return code

	return fallback_code
