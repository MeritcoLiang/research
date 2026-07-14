"""Jurisdiction-aware source registry and query plan for AIDC research."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .models import AIDCResearchRequest


@dataclass(frozen=True, slots=True)
class SourceTarget:
    name: str
    category: str
    authority_grade: str
    url: str
    primary: bool
    search_terms: tuple[str, ...]
    purpose: str

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc


@dataclass(frozen=True, slots=True)
class JurisdictionSourceRegistry:
    state: str
    county: str
    targets: tuple[SourceTarget, ...]
    lifecycle_terms: tuple[str, ...] = field(default_factory=tuple)
    identity_terms: tuple[str, ...] = field(default_factory=tuple)

    def render_for_prompt(self, request: AIDCResearchRequest) -> str:
        aliases = [request.name, *request.aliases, *request.location_hints]
        alias_text = ", ".join(aliases)
        lines = [
            f"Jurisdiction source registry: {self.county}, {self.state}",
            f"Seed identities and location hints: {alias_text}",
            "Search these targets in priority order; URLs are entry points, not proof by themselves:",
        ]
        for index, target in enumerate(self.targets, start=1):
            terms = ", ".join(target.search_terms)
            lines.append(
                f"{index}. [{target.authority_grade}] {target.name} | {target.category} | "
                f"primary={target.primary} | {target.url} | terms={terms} | purpose={target.purpose}"
            )
        lines.append("Identity terms: " + ", ".join(self.identity_terms))
        lines.append("Lifecycle terms: " + ", ".join(self.lifecycle_terms))
        return "\n".join(lines)

    def build_search_queries(self, request: AIDCResearchRequest) -> list[str]:
        """Create deterministic seed queries for tests, logs, and prompt guidance."""

        identities = [request.name, *request.aliases, *request.location_hints]
        queries: list[str] = []
        for target in self.targets:
            terms = " OR ".join(f'"{term}"' for term in target.search_terms[:4])
            for identity in identities:
                queries.append(
                    f'site:{target.domain} "{identity}" "{request.county}" ({terms})'
                )
        return _dedupe(queries)


COMMON_IDENTITY_TERMS = (
    "project code name",
    "applicant",
    "property owner",
    "owner LLC",
    "developer",
    "engineering firm",
    "address",
    "parcel ID",
    "PIN",
    "case number",
    "permit number",
    "substation name",
)

COMMON_LIFECYCLE_TERMS = (
    "rezoning",
    "zoning map amendment",
    "special exception",
    "special use permit",
    "conditional use permit",
    "site plan",
    "staff report",
    "public hearing",
    "grading permit",
    "land disturbance permit",
    "building permit",
    "foundation permit",
    "shell permit",
    "inspection",
    "temporary certificate of occupancy",
    "certificate of occupancy",
    "air permit",
    "stormwater permit",
    "Section 404",
    "transmission line",
    "substation",
    "CPCN",
    "in-service date",
    "water line",
    "sewer",
    "road improvement",
    "tax incentive",
    "lawsuit",
    "injunction",
)


def get_source_registry(state: str, county: str) -> JurisdictionSourceRegistry:
    key = (state.strip().casefold(), county.strip().casefold())
    if key in {
        ("virginia", "loudoun county"),
        ("va", "loudoun county"),
        ("virginia", "loudoun"),
        ("va", "loudoun"),
    }:
        return LOUDOUN_VIRGINIA_REGISTRY
    return _generic_registry(state=state, county=county)


LOUDOUN_VIRGINIA_REGISTRY = JurisdictionSourceRegistry(
    state="Virginia",
    county="Loudoun County",
    identity_terms=COMMON_IDENTITY_TERMS,
    lifecycle_terms=COMMON_LIFECYCLE_TERMS,
    targets=(
        SourceTarget(
            name="Loudoun County Planning and Zoning",
            category="planning_and_zoning",
            authority_grade="A/B",
            url="https://www.loudoun.gov/173/Planning-Zoning",
            primary=True,
            search_terms=("data center", "rezoning", "special exception", "site plan", "staff report"),
            purpose="Find land-use cases, application numbers, staff reports, proffers, maps, and approval conditions.",
        ),
        SourceTarget(
            name="Loudoun County Public Hearing Information",
            category="agenda_and_hearings",
            authority_grade="A/B",
            url="https://www.loudoun.gov/1889/Public-Hearing-Information",
            primary=True,
            search_terms=("Planning Commission", "Board of Supervisors", "public hearing", "agenda packet", "minutes"),
            purpose="Verify hearing dates, recommendations, final votes, deferrals, withdrawals, and amendments.",
        ),
        SourceTarget(
            name="Loudoun County LandMARC",
            category="land_management_cases",
            authority_grade="A/B",
            url="https://www.loudoun.gov/3362/LandMARC",
            primary=True,
            search_terms=("application", "case", "parcel", "plan", "permit"),
            purpose="Resolve case identifiers, parcel relationships, application status, and attached plans.",
        ),
        SourceTarget(
            name="Loudoun County Building and Development Permitting",
            category="building_and_grading_permits",
            authority_grade="A",
            url="https://www.loudoun.gov/4264/Permitting",
            primary=True,
            search_terms=("grading permit", "land disturbance", "building permit", "inspection", "certificate of occupancy"),
            purpose="Distinguish entitlement from physical construction and identify commissioning or occupancy milestones.",
        ),
        SourceTarget(
            name="Loudoun County Mapping and GIS",
            category="property_and_gis",
            authority_grade="A/B",
            url="https://www.loudoun.gov/191/Mapping-GIS",
            primary=True,
            search_terms=("parcel", "PIN", "property owner", "address", "tax map"),
            purpose="Resolve the exact site, parcel IDs, ownership, neighboring infrastructure, and incorporated jurisdiction.",
        ),
        SourceTarget(
            name="Loudoun County Board of Supervisors",
            category="board_actions_and_development_agreements",
            authority_grade="A",
            url="https://www.loudoun.gov/87/Board-of-Supervisors",
            primary=True,
            search_terms=("agenda", "action report", "resolution", "development agreement", "data center"),
            purpose="Confirm final legislative actions, agreements, appropriations, and official progress updates.",
        ),
        SourceTarget(
            name="Virginia Department of Environmental Quality",
            category="environmental_permits",
            authority_grade="A/B",
            url="https://www.deq.virginia.gov/permits",
            primary=True,
            search_terms=("data center", "air permit", "generator", "stormwater", "public notice"),
            purpose="Find air, construction stormwater, water, generator, and public-notice records.",
        ),
        SourceTarget(
            name="Virginia State Corporation Commission DocketSearch",
            category="power_and_transmission",
            authority_grade="A/B",
            url="https://www.scc.virginia.gov/docketsearch/",
            primary=True,
            search_terms=("transmission", "substation", "certificate", "Loudoun", "in-service"),
            purpose="Find transmission applications, exhibits, load descriptions, hearing records, and target in-service dates.",
        ),
        SourceTarget(
            name="USACE Norfolk District Public Notices",
            category="wetlands_and_section_404",
            authority_grade="A/B",
            url="https://www.nao.usace.army.mil/Media/Public-Notices/",
            primary=True,
            search_terms=("data center", "Loudoun", "Section 404", "wetlands", "public notice"),
            purpose="Find wetland and stream-impact permits with site plans, acreage, phased buildings, and substations.",
        ),
        SourceTarget(
            name="Dominion Energy electric projects",
            category="utility_projects",
            authority_grade="B",
            url="https://www.dominionenergy.com/projects-and-facilities/electric-projects",
            primary=True,
            search_terms=("Loudoun", "transmission", "substation", "project", "open house"),
            purpose="Corroborate utility project names, routes, construction notices, and in-service schedules.",
        ),
        SourceTarget(
            name="Loudoun Water",
            category="water_and_sewer",
            authority_grade="B",
            url="https://www.loudounwater.org/",
            primary=True,
            search_terms=("capital project", "water main", "sewer", "Stone Ridge", "Reeds Farm"),
            purpose="Check water, reclaimed-water, sewer, pumping, and capital-project dependencies.",
        ),
        SourceTarget(
            name="Virginia Economic Development Partnership",
            category="economic_development_and_incentives",
            authority_grade="B",
            url="https://www.vedp.org/",
            primary=True,
            search_terms=("Amazon", "AWS", "data center", "investment", "incentive"),
            purpose="Find announced investment, incentives, code names, and company identity clues.",
        ),
        SourceTarget(
            name="Loudoun Now",
            category="local_news",
            authority_grade="C",
            url="https://www.loudounnow.com/",
            primary=False,
            search_terms=("data center", "Stone Ridge", "Reeds Farm", "Amazon", "AWS"),
            purpose="Find local reporting, official interviews, community reaction, and references to records not yet indexed.",
        ),
        SourceTarget(
            name="Loudoun Times-Mirror",
            category="local_news",
            authority_grade="C",
            url="https://www.loudountimes.com/",
            primary=False,
            search_terms=("data center", "Stone Ridge", "Reeds Farm", "Amazon", "AWS"),
            purpose="Find local hearings, construction observations, litigation, and community issues.",
        ),
        SourceTarget(
            name="The Burn",
            category="hyperlocal_news",
            authority_grade="C/D",
            url="https://www.theburn.com/",
            primary=False,
            search_terms=("data center", "Stone Ridge", "Reeds Farm Lane", "construction"),
            purpose="Use as a discovery source for address-level and on-site developments; verify all material claims elsewhere.",
        ),
        SourceTarget(
            name="Washington Business Journal",
            category="regional_business_news",
            authority_grade="C",
            url="https://www.bizjournals.com/washington/",
            primary=False,
            search_terms=("AWS", "Amazon", "Loudoun", "data center", "land"),
            purpose="Find land transactions, developer identities, contractors, investment, and schedule claims.",
        ),
    ),
)


def _generic_registry(*, state: str, county: str) -> JurisdictionSourceRegistry:
    return JurisdictionSourceRegistry(
        state=state,
        county=county,
        identity_terms=COMMON_IDENTITY_TERMS,
        lifecycle_terms=COMMON_LIFECYCLE_TERMS,
        targets=(
            SourceTarget(
                name=f"{county} official government",
                category="county_government",
                authority_grade="A/B",
                url="https://www.usa.gov/local-governments",
                primary=True,
                search_terms=("planning", "zoning", "permit", "agenda", "GIS"),
                purpose="Discover the authoritative county, city, town, or township portals before project research.",
            ),
            SourceTarget(
                name=f"{state} environmental agency",
                category="environmental_permits",
                authority_grade="A/B",
                url="https://www.epa.gov/aboutepa/health-and-environmental-agencies-us-states-and-territories",
                primary=True,
                search_terms=("air permit", "stormwater", "water permit", "public notice"),
                purpose="Discover the state environmental permitting authority and project records.",
            ),
            SourceTarget(
                name=f"{state} utility commission",
                category="power_and_transmission",
                authority_grade="A/B",
                url="https://www.naruc.org/about-naruc/regulatory-commissions/",
                primary=True,
                search_terms=("transmission", "substation", "large load", "CPCN"),
                purpose="Discover the state docket system and power-infrastructure proceedings.",
            ),
        ),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
