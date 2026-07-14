from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .models import AIDCResearchRequest


@dataclass(frozen=True, slots=True)
class SourceTarget:
    name: str
    category: str
    grade: str
    url: str
    search_terms: tuple[str, ...]
    purpose: str

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    state: str
    county: str
    targets: tuple[SourceTarget, ...]

    def render(self, request: AIDCResearchRequest) -> str:
        identities = [request.name, *request.aliases, *request.location_hints]
        lines = [
            f"Jurisdiction source map: {self.county}, {self.state}",
            "Seed identities: " + ", ".join(identities),
            "Entry points are discovery targets, not evidence by themselves:",
        ]
        for index, target in enumerate(self.targets, 1):
            lines.append(
                f"{index}. [{target.grade}] {target.name} | {target.category} | {target.url} | "
                f"terms={', '.join(target.search_terms)} | {target.purpose}"
            )
        return "\n".join(lines)

    def queries(self, request: AIDCResearchRequest) -> list[str]:
        identities = [request.name, *request.aliases, *request.location_hints]
        output: list[str] = []
        for target in self.targets:
            terms = " OR ".join(f'\"{term}\"' for term in target.search_terms[:4])
            for identity in identities:
                output.append(f'site:{target.domain} "{identity}" "{request.county}" ({terms})')
        return list(dict.fromkeys(output))


LOUDOUN = SourceRegistry(
    state="Virginia",
    county="Loudoun County",
    targets=(
        SourceTarget("Loudoun Planning and Zoning", "planning", "A/B", "https://www.loudoun.gov/173/Planning-Zoning", ("data center", "rezoning", "special exception", "site plan"), "Find cases, staff reports, proffers, maps, and approval conditions."),
        SourceTarget("Loudoun Public Hearings", "hearings", "A/B", "https://www.loudoun.gov/1889/Public-Hearing-Information", ("Planning Commission", "Board of Supervisors", "agenda packet", "minutes"), "Verify hearings, votes, deferrals, withdrawals, and amendments."),
        SourceTarget("Loudoun LandMARC", "land_management", "A/B", "https://www.loudoun.gov/3362/LandMARC", ("application", "case", "parcel", "plan"), "Resolve case identifiers, parcels, status, and attached plans."),
        SourceTarget("Loudoun Permitting", "permits", "A", "https://www.loudoun.gov/4264/Permitting", ("grading permit", "land disturbance", "building permit", "certificate of occupancy"), "Separate entitlement, site work, vertical construction, and occupancy."),
        SourceTarget("Loudoun GIS", "property_gis", "A/B", "https://www.loudoun.gov/191/Mapping-GIS", ("parcel", "PIN", "property owner", "address"), "Resolve exact site, ownership, parcels, and jurisdiction."),
        SourceTarget("Virginia DEQ", "environment", "A/B", "https://www.deq.virginia.gov/permits", ("air permit", "generator", "stormwater", "public notice"), "Find air, stormwater, water, and equipment records."),
        SourceTarget("Virginia SCC DocketSearch", "power", "A/B", "https://www.scc.virginia.gov/docketsearch/", ("transmission", "substation", "certificate", "in-service"), "Find power filings, load descriptions, routes, and schedules."),
        SourceTarget("USACE Norfolk Public Notices", "wetlands", "A/B", "https://www.nao.usace.army.mil/Media/Public-Notices/", ("Section 404", "wetlands", "stream", "data center"), "Find wetland/stream impacts and site plans."),
        SourceTarget("Dominion Electric Projects", "utility", "B", "https://www.dominionenergy.com/projects-and-facilities/electric-projects", ("Loudoun", "transmission", "substation", "open house"), "Corroborate routes, notices, construction, and in-service dates."),
        SourceTarget("Loudoun Water", "water_sewer", "B", "https://www.loudounwater.org/", ("capital project", "water main", "sewer", "pump station"), "Check water, reclaimed water, sewer, and pumping dependencies."),
        SourceTarget("Loudoun Now", "local_news", "C", "https://www.loudounnow.com/", ("data center", "construction", "hearing", "lawsuit"), "Discover local developments and referenced records."),
        SourceTarget("Loudoun Times-Mirror", "local_news", "C", "https://www.loudountimes.com/", ("data center", "construction", "appeal", "community"), "Discover hearings, construction, litigation, and community issues."),
    ),
)


def get_registry(state: str, county: str) -> SourceRegistry:
    state_key = state.strip().casefold()
    county_key = county.strip().casefold()
    if state_key in {"virginia", "va"} and county_key in {"loudoun", "loudoun county"}:
        return LOUDOUN
    return SourceRegistry(
        state=state,
        county=county,
        targets=(
            SourceTarget(f"{county} official government", "county_government", "A/B", "https://www.usa.gov/local-governments", ("planning", "zoning", "permit", "agenda"), "Discover authoritative local portals and records."),
            SourceTarget(f"{state} environmental agency", "environment", "A/B", "https://www.epa.gov/aboutepa/health-and-environmental-agencies-us-states-and-territories", ("air permit", "stormwater", "water permit", "public notice"), "Discover the state environmental authority."),
            SourceTarget(f"{state} utility commission", "power", "A/B", "https://www.naruc.org/about-naruc/regulatory-commissions/", ("transmission", "substation", "large load", "certificate"), "Discover the state docket system and power records."),
        ),
    )
