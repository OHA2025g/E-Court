"""Static master data constants for the eCourts PMIS."""

HIGH_COURTS = [
    "Allahabad", "Andhra Pradesh", "Bombay", "Calcutta", "Chhattisgarh",
    "Delhi", "Gauhati – Arunachal Pradesh", "Gauhati – Assam",
    "Gauhati – Mizoram", "Gauhati - Nagaland", "Gujarat", "Himachal Pradesh",
    "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Madras", "Manipur", "Meghalaya", "Odisha", "Patna",
    "Punjab & Haryana", "Rajasthan", "Sikkim", "Telangana",
    "Tripura", "Uttarakhand",
]

# 17 BRD-canonical components in order
COMPONENTS = [
    {"code": "ESK", "name": "e-Sewa Kendras", "uom": "Count"},
    {"code": "PLC", "name": "Paperless Courts", "uom": "Count"},
    {"code": "EVC", "name": "Expansion of Virtual Courts", "uom": "Count"},
    {"code": "LST", "name": "Live Streaming", "uom": "Count"},
    {"code": "DCR", "name": "Digitisation of Court Records", "uom": "Crore Pages"},
    {"code": "VCU", "name": "Video Conferencing Upgrade", "uom": "Count"},
    {"code": "SOL", "name": "Solar Power for ICT", "uom": "Count"},
    {"code": "AHW", "name": "Additional Hardware — Phase I & II", "uom": "Count"},
    {"code": "NSC", "name": "ICT for Newly Set-Up Courts", "uom": "Count"},
    {"code": "S3W", "name": "HC & DC Website Migration — S3WaaS", "uom": "Count"},
    {"code": "CCS", "name": "Cloud Computing & Storage", "uom": "PB"},
    {"code": "ICT", "name": "ICT Training / Change Management", "uom": "Count"},
    {"code": "NST", "name": "NSTEP Expansion", "uom": "Count"},
    {"code": "SWD", "name": "Software Development", "uom": "Count"},
    {"code": "PMU", "name": "PMU in e-Committee & DoJ", "uom": "Percentage"},
    {"code": "CON", "name": "Connectivity — Primary + Redundancy", "uom": "Count"},
    {"code": "EOF", "name": "e-Office for HCs & District Courts", "uom": "Count"},
]

# Map component → list of physical indicators
COMPONENT_INDICATORS = {
    "e-Sewa Kendras": [
        "No of sites prepared (in Absolute Count)",
        "No of e-sewa kendras in court complexes (in Absolute Count)",
        "No of e-sewa kendra functional (in Absolute Count)",
        "No of e-sewa kendras Setup with Porta cabin (in Absolute Count)",
        "No of e-sewa kendras Setup within existing court complex space (in Absolute Count)",
        "No of e-sewa kendras Provided with functional internet (in Absolute Count)",
    ],
    "Paperless Courts": [
        "No of paperless courts (in Absolute Count)",
        "No of court rooms with VC enabled (in Absolute Count)",
        "No of court rooms with Led Display (in Absolute Count)",
        "No of court rooms with Scanner Deployed (in Absolute Count)",
        "No of court rooms with Computer system installed (in Absolute Count)",
        "No of court rooms with Speech to text enabled (in Absolute Count)",
    ],
    "Expansion of Virtual Courts": [
        "No of sites prepared (in Absolute Count)",
        "No of virtual courts operational (in Absolute Count)",
        "No of court rooms with VC enabled (in Absolute Count)",
        "No of court rooms with Led Display (in Absolute Count)",
        "No of court rooms with Scanner Deployed (in Absolute Count)",
        "No of court rooms with Computer system installed (in Absolute Count)",
        "No of court rooms with Speech to text enabled (in Absolute Count)",
    ],
    "Live Streaming": [
        "No of sites prepared (in Absolute Count)",
        "No of court rooms enabled for live streaming (in Absolute Count)",
        "No of court rooms with VC enabled (in Absolute Count)",
        "No of court rooms with Led Display (in Absolute Count)",
        "No of court rooms with Scanner Deployed (in Absolute Count)",
        "No of court rooms with Computer system installed (in Absolute Count)",
        "No of court rooms with Speech to text enabled (in Absolute Count)",
        "No of document visualiser installed (in Absolute Count)",
    ],
    "Digitisation of Court Records": [
        "No of pages digitized (in Cr.)",
        "No of pages (of active cases) digitized (in Cr.)",
        "No of pages (of legacy cases) digitized (in Cr.)",
    ],
    "Video Conferencing Upgrade": [
        "No of video conference units installed (in Absolute Count)",
        "No of video conference units functional (in Absolute Count)",
        "No of video conference installed in district govt hospitals (in Absolute Count)",
        "No of video conference installed in Jails (in Absolute Count)",
        "No of video conference installed in Courts + DSA (in Absolute Count)",
    ],
    "Solar Power for ICT": [
        "No of solar panels installed (in Absolute Count)",
    ],
    "Additional Hardware — Phase I & II": [
        "No of Courts upgraded with new infrastructure (in Absolute Count)",
    ],
    "ICT for Newly Set-Up Courts": [
        "No of new Courts covered (in Absolute Count)",
    ],
    "HC & DC Website Migration — S3WaaS": [
        "No of District Court websites migrated (in Absolute Count)",
        "No of visitors to the migrated District Court websites (in Absolute Count)",
    ],
    "Cloud Computing & Storage": [
        "Total centralised storage capacity (in PB)",
    ],
    "ICT Training / Change Management": [
        "No of training programmes conducted (in Absolute Count)",
    ],
    "NSTEP Expansion": [
        "No of Court Establishments covered (in Absolute Count)",
        "No of hand held devices deployed (in Absolute Count)",
    ],
    "Software Development": [
        "No of technical support team members recruited (in Absolute Count)",
    ],
    "PMU in e-Committee & DoJ": [
        "Percentage of project targets achieved (in %)",
    ],
    "Connectivity — Primary + Redundancy": [
        "No of New Court Complexes Connected through WAN (in Absolute Count)",
    ],
    "e-Office for HCs & District Courts": [
        "No of Courts implemented e-Office (in Absolute Count)",
    ],
}

# 19 Outcome subjects per BRD
OUTCOME_SUBJECTS = [
    "eFiling", "Automated eMail", "SMS", "ICJS", "NSTEP", "Virtual Courts",
    "ePay", "Mobile App", "Video Conferencing", "JustIS Mobile App", "NAPIX",
    "DC Services Portal", "eSewa Kendra", "Digitization of Case Records",
    "Solar Facilities", "eOffice", "Touch Screen Kiosks", "Change Management",
    "Paperless Courts",
]

# Map raw outcome subjects (from Excel) → canonical BRD subjects
OUTCOME_SUBJECT_MAP = {
    "eFiling": "eFiling",
    "Automated eMail": "Automated eMail",
    "SMS": "SMS",
    "Paperless Courts (miscellaneous)": "Paperless Courts",
    "Paperless Courts": "Paperless Courts",
    "ICJS": "ICJS",
    "NSTEP": "NSTEP",
    "Virtual Courts": "Virtual Courts",
    "ePay": "ePay",
    "Mobile app": "Mobile App",
    "Software Development": "Mobile App",
    "JustIS mobile app": "JustIS Mobile App",
    "Video conferencing": "Video Conferencing",
    "NAPIX": "NAPIX",
    "District Courts  services portal": "DC Services Portal",
    "S3waaS": "DC Services Portal",
    "eSewa Kendra": "eSewa Kendra",
    "Digitization of Case Records": "Digitization of Case Records",
    "Solar Facilities": "Solar Facilities",
    "eOffice": "eOffice",
    "Infra for New court Complexes": "Touch Screen Kiosks",
    "Touch Screen Kiosks": "Touch Screen Kiosks",
    "Change Management": "Change Management",
}

DEFAULT_RAG_THRESHOLDS = {"green_min": 80.0, "amber_min": 65.0}

# Reporting months: baseline (Sep 2023–May 2026 cumulative) + monthly from Jun 2026
REPORTING_PERIODS = [
    {"period": "2026-05", "label": "Baseline (Sep 2023 – May 2026)", "is_baseline": True},
    {"period": "2026-06", "label": "June 2026", "is_baseline": False},
    {"period": "2026-07", "label": "July 2026", "is_baseline": False},
    {"period": "2026-08", "label": "August 2026", "is_baseline": False},
    {"period": "2026-09", "label": "September 2026", "is_baseline": False},
    {"period": "2026-10", "label": "October 2026", "is_baseline": False},
    {"period": "2026-11", "label": "November 2026", "is_baseline": False},
    {"period": "2026-12", "label": "December 2026", "is_baseline": False},
    {"period": "2027-01", "label": "January 2027", "is_baseline": False},
    {"period": "2027-02", "label": "February 2027", "is_baseline": False},
]

# Sample DPR deliverables
DPR_DELIVERABLES = [
    {"code": "DPR-001", "title": "Approval of Detailed Project Report by Cabinet", "owner": "DoJ", "target_date": "2024-09-30", "status": "Completed"},
    {"code": "DPR-002", "title": "Empanelment of System Integrators", "owner": "DoJ/PMU", "target_date": "2024-12-31", "status": "Completed"},
    {"code": "DPR-003", "title": "Roll-out of e-Sewa Kendras across 28 HCs", "owner": "High Courts", "target_date": "2026-12-31", "status": "In Progress"},
    {"code": "DPR-004", "title": "Digitisation of 3,000 Cr pages of legacy records", "owner": "High Courts/SI", "target_date": "2027-03-31", "status": "In Progress"},
    {"code": "DPR-005", "title": "Operationalisation of Cloud Computing infrastructure", "owner": "PMU/SI", "target_date": "2026-06-30", "status": "In Progress"},
    {"code": "DPR-006", "title": "Migration of all DC websites to S3WaaS", "owner": "High Courts", "target_date": "2027-06-30", "status": "Not Started"},
    {"code": "DPR-007", "title": "Setup of PMU in e-Committee and DoJ", "owner": "DoJ", "target_date": "2024-12-31", "status": "Completed"},
    {"code": "DPR-008", "title": "Connectivity (Primary + Redundancy) for all complexes", "owner": "PMU/SI", "target_date": "2027-12-31", "status": "In Progress"},
    {"code": "DPR-009", "title": "e-Office roll-out to all High Courts", "owner": "High Courts", "target_date": "2027-09-30", "status": "In Progress"},
    {"code": "DPR-010", "title": "NSTEP expansion to all States/UTs", "owner": "High Courts", "target_date": "2027-06-30", "status": "In Progress"},
]
