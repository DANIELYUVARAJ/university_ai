"""
University DataShield – Detection Engine
Phase 9: context.py

Cross-field and dataset-level contextual detection intelligence.
Analyzes co-occurring fields in a dataset schema to reinforce confidence
and explain cross-field relationships without falsely classifying safe fields.
"""

from __future__ import annotations
from typing import List, Set, Tuple
from .normalizer import normalize_field_name, get_field_tokens
from .schemas import FieldInput


class DatasetContext:
    """
    Contextual model derived from scanning all fields present in a schema.
    Detects thematic clusters and computes cross-field co-occurrence signals.
    """

    def __init__(self, fields: List[FieldInput]):
        self.raw_fields = fields
        self.normalized_names = [normalize_field_name(f.name) for f in fields]
        self.name_set: Set[str] = set(self.normalized_names)

        # Thematic cluster detection across schema
        self.has_direct_id_cluster = bool(
            self.name_set
            & {
                "student_id",
                "student_name",
                "first_name",
                "last_name",
                "full_name",
                "email",
                "personal_email",
                "student_email",
                "phone",
                "mobile_number",
                "roll_number",
                "candidate_id",
                "candidate_reference",
                "registration_number",
            }
        )

        self.has_academic_cluster = bool(
            self.name_set
            & {
                "course_code",
                "course_name",
                "subject",
                "semester",
                "gpa",
                "cgpa",
                "grade",
                "marks",
                "exam_score",
                "attendance",
                "attendance_percentage",
                "absence_count",
                "internal_mark",
            }
        )

        self.has_placement_cluster = bool(
            self.name_set
            & {
                "placement_package",
                "placement_status",
                "company",
                "company_name",
                "company_code",
                "salary",
                "package",
                "ctc",
                "offer_status",
                "employer",
            }
        )

        self.has_contact_cluster = bool(
            self.name_set
            & {
                "email",
                "phone",
                "mobile",
                "mobile_number",
                "contact_number",
                "address",
                "guardian_contact",
                "personal_contact",
            }
        )

    def get_field_context_signals(self, field_name: str) -> Tuple[int, List[str]]:
        """
        Evaluate cross-field contextual reinforcement for a specific field.
        Returns (confidence_boost, contextual_reasons).
        """
        norm = normalize_field_name(field_name)
        boost = 0
        reasons: List[str] = []

        # 1. Ambiguous 'contact' co-occurring with direct contact identifiers
        if norm == "contact" and self.has_contact_cluster:
            boost += 15
            reasons.append(
                "Co-occurs with direct contact identifiers (strengthens personal contact classification)"
            )

        # 2. Placement co-occurrence (e.g. salary + placement_package + company)
        if (
            norm in ("salary", "placement_package", "offer_status", "ctc")
            and self.has_placement_cluster
        ):
            boost += 10
            reasons.append(
                "Co-occurs with placement/employer attributes (confirms placement compensation context)"
            )

        # 3. Academic co-occurrence (e.g. absence_count, internal_mark + course_code, semester)
        if (
            norm
            in (
                "absence_count",
                "internal_mark",
                "attendance_percentage",
                "exam_score",
                "grade",
            )
            and self.has_academic_cluster
        ):
            boost += 10
            reasons.append(
                "Co-occurs with academic/curriculum attributes (confirms academic record context)"
            )

        # 4. Candidate / student reference with student identifiers
        if (
            norm in ("candidate_id", "candidate_reference", "student_reference")
            and self.has_direct_id_cluster
        ):
            boost += 15
            reasons.append(
                "Co-occurs with student registry attributes (confirms student identifier context)"
            )

        # 5. Paired name components (first_name + last_name)
        if (
            "first_name" in self.name_set
            and "last_name" in self.name_set
            and norm in ("first_name", "last_name")
        ):
            boost += 10
            reasons.append("Co-occurs as paired first_name/last_name persona components")

        # 6. Date of birth + address co-occurrence (quasi-identifier linkage risk)
        if (
            norm in ("date_of_birth", "dob", "birth_date", "birth_year")
            and ("address" in self.name_set or "postal_code" in self.name_set)
        ):
            boost += 10
            reasons.append(
                "Co-occurs with address/demographics (elevates quasi-identifier linkage potential)"
            )

        return boost, reasons
