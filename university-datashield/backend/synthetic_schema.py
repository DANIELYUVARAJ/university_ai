"""
University DataShield – Synthetic Data
Phase 2: synthetic_schema.py

A pre-built synthetic dataset schema used for demonstration and testing.

IMPORTANT: All 'sample_pattern' values are SYNTHETIC.
No real student names, IDs, emails, or phone numbers are used here.
"""

from __future__ import annotations

SYNTHETIC_SCHEMA = {
    "dataset_name": "university_synthetic_demo",
    "fields": [
        {
            "name": "student_id",
            "data_type": "string",
            "sample_pattern": "STU_DEMO_001",
        },
        {
            "name": "student_name",
            "data_type": "string",
            "sample_pattern": "Demo Student",
        },
        {
            "name": "email",
            "data_type": "string",
            "sample_pattern": "student001@example.edu",
        },
        {
            "name": "phone",
            "data_type": "string",
            "sample_pattern": "+91-9000000001",
        },
        {
            "name": "date_of_birth",
            "data_type": "date",
            "sample_pattern": "1999-04-17",
        },
        {
            "name": "attendance_percentage",
            "data_type": "number",
            "sample_pattern": "92",
        },
        {
            "name": "exam_score",
            "data_type": "number",
            "sample_pattern": "78",
        },
        {
            "name": "placement_status",
            "data_type": "string",
            "sample_pattern": "Placed",
        },
        {
            "name": "placement_package",
            "data_type": "number",
            "sample_pattern": "850000",
        },
        {
            "name": "course_code",
            "data_type": "string",
            "sample_pattern": "CS401",
        },
        {
            "name": "contact",
            "data_type": "string",
            "sample_pattern": "student001@example.edu",
        },
        {
            "name": "email_template_id",
            "data_type": "string",
            "sample_pattern": "TPL_001",
        },
        {
            "name": "student_identifier",
            "data_type": "string",
            "sample_pattern": "STU_DEMO_001",
        },
        {
            "name": "guardian_contact",
            "data_type": "string",
            "sample_pattern": "+91-9000000002",
        },
    ],
}
