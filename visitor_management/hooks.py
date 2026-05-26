app_name = "visitor_management"
app_title = "Visitor Management"
app_publisher = "FnD Corp"
app_description = "Visitor Aps"
app_email = "silver_efendy@yahoo.co.id"
app_license = "mit"

doc_events = {
    "Visitor": {
        "validate": (
            "visitor_management.visitor_management.services.visitor_service.validate_duplicate_active"
        )
    }
}

scheduler_events = {
    "hourly": [
        "visitor_management.visitor_management.tasks.visitor_tasks.auto_checkout_stale_visitors"
    ]
}
