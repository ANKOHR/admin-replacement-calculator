"""Fixed fictional fixtures; no random generation or seed required."""
from pathlib import Path

FIXTURES = {
    "inbox-triage.md": """# Fictional inbox-triage admin
Synthetic: yes
Weekly hours: 40
## Tools
- Fictional mailbox
- Fictional spreadsheet
## Responsibilities
- 70%: Categorize structured inbox messages using fixed rules; route structured messages using fixed rules
- 20%: Send template acknowledgements using fixed rules
- 10%: Resolve disputes with discretion and relationship judgment
""",
    "client-coordinator.md": """# Fictional client-facing coordinator
Synthetic: yes
Weekly hours: 40
## Tools
- Fictional CRM
- Fictional calendar
## Responsibilities
- 60%: Negotiate client priorities and maintain relationships
- 20%: Decide ambiguous client requests with discretion
- 10%: Draft responses for sensitive client requests for human approval
- 10%: Schedule structured appointments using fixed rules
""",
    "bookkeeping.md": """# Fictional mixed bookkeeping role
Synthetic: yes
Weekly hours: 40
## Tools
- Fictional ledger
- Fictional spreadsheet
## Responsibilities
- 40%: Match structured invoices using exact rules
- 30%: Prepare reconciliation summaries for human judgment
- 20%: Resolve disputes with discretion
- 10%: Record structured payments using fixed rules
""",
    "malformed.md": """# Fictional malformed role
Synthetic: yes
Weekly hours: 40
## Tools
- Fictional mailbox
## Responsibilities
- 80%: Route structured messages using fixed rules
- 30%: Decide ambiguous requests
""",
}


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in FIXTURES.items():
        (directory / name).write_bytes(content.encode("utf-8"))
    return sorted(FIXTURES)
