"""Права на кадровую загрузку и выгрузку персональных сведений."""

from apps.reports.registry import FILTER_REPORT_PERMISSIONS

IMPORT_PERMISSIONS = (
    "legacy.add_importbatch",
    "personnel.add_person",
    "personnel.change_person",
    "military.add_militaryrecord",
    "military.change_militaryrecord",
    "military.add_commissariatregistration",
    "military.change_commissariatregistration",
    "military.add_reservationdismissal",
    "military.delete_reservationdismissal",
    *(
        f"personnel.{action}_{model}"
        for action in ("add", "change")
        for model in (
            "identitydocument",
            "address",
            "relative",
            "education",
            "assignment",
            "additionalattribute",
        )
    ),
)
EXPORT_PERMISSIONS = (
    *FILTER_REPORT_PERMISSIONS,
    "military.view_commissariatregistration",
)
