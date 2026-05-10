from __future__ import annotations

import random
from dataclasses import dataclass

from faker import Faker

fake = Faker()


@dataclass
class TaxProfile:
    full_name: str
    email: str
    ssn_last4: str
    employer: str
    wages: int           # cents
    federal_withheld: int
    state: str
    filing_status: str
    has_1099: bool
    income_1099: int     # cents


def generate_tax_profile() -> TaxProfile:
    wages = random.randint(30_000, 150_000) * 100
    return TaxProfile(
        full_name=fake.name(),
        email=fake.email(),
        ssn_last4=str(random.randint(1000, 9999)),
        employer=fake.company(),
        wages=wages,
        federal_withheld=int(wages * random.uniform(0.12, 0.22)),
        state=fake.state_abbr(),
        filing_status=random.choice(["single", "married_jointly", "head_of_household"]),
        has_1099=random.random() > 0.5,
        income_1099=random.randint(500, 20_000) * 100,
    )
