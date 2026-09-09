#!/usr/bin/env python3
"""Validate the three remotely published VATROC CDM data files.

The validator deliberately checks syntax and unambiguous logical conflicts only.
Operational values such as rates, taxi times, and SID separation minutes are not
compared with policy constants, so legitimate operational changes remain possible.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


AIRPORT_RE = re.compile(r"[A-Z]{4}")
RUNWAY_RE = re.compile(r"(?:0[1-9]|[12][0-9]|3[0-6])[LCR]?")
SID_RE = re.compile(r"[A-Z0-9]+")


@dataclass(frozen=True)
class Location:
    path: Path
    line: int


@dataclass(frozen=True)
class RateRule:
    location: Location
    airport: str
    arrival: tuple[str, ...] | None
    not_arrival: tuple[str, ...] | None
    departure: tuple[str, ...] | None
    not_departure: tuple[str, ...] | None
    dependent: tuple[str, ...] | None
    rates: tuple[tuple[int, int], ...]

    @property
    def selector(self) -> tuple[object, ...]:
        return (
            self.airport,
            self.arrival,
            self.not_arrival,
            self.departure,
            self.not_departure,
            self.dependent,
        )


@dataclass(frozen=True)
class SidRule:
    location: Location
    airport: str
    runway1: str
    sid1: str
    runway2: str
    sid2: str
    minutes: Decimal

    @property
    def pair(self) -> tuple[tuple[str, str], tuple[str, str]]:
        return tuple(sorted(((self.runway1, self.sid1), (self.runway2, self.sid2))))  # type: ignore[return-value]


@dataclass(frozen=True)
class TaxiZone:
    location: Location
    airport: str
    runway: str
    points: tuple[tuple[float, float], ...]
    minutes: int


class Validator:
    def __init__(self, root: Path, *, annotations: bool = True) -> None:
        self.root = root
        self.annotations = annotations
        self.errors = 0
        self.warnings = 0
        self.rates: list[RateRule] = []
        self.sid_rules: list[SidRule] = []
        self.taxi_zones: list[TaxiZone] = []

    def report(self, level: str, location: Location, message: str) -> None:
        if level == "error":
            self.errors += 1
        else:
            self.warnings += 1

        try:
            display_path = location.path.relative_to(self.root).as_posix()
        except ValueError:
            display_path = location.path.as_posix()

        if self.annotations:
            safe_message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::{level} file={display_path},line={location.line}::{safe_message}")
        else:
            print(f"{display_path}:{location.line}: {level}: {message}")

    def error(self, location: Location, message: str) -> None:
        self.report("error", location, message)

    def warning(self, location: Location, message: str) -> None:
        self.report("warning", location, message)

    def data_lines(self, filename: str) -> list[tuple[Location, str]]:
        path = self.root / filename
        if not path.is_file():
            self.error(Location(path, 1), "required file is missing")
            return []

        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            self.error(Location(path, 1), "file must be valid UTF-8")
            return []

        result: list[tuple[Location, str]] = []
        for number, raw in enumerate(text.splitlines(), 1):
            location = Location(path, number)
            if not raw.strip():
                continue
            if raw.startswith("#"):
                continue
            if raw.lstrip().startswith("#"):
                self.error(location, "comments must start with # in column 1")
                continue
            if raw != raw.strip():
                self.error(location, "data lines must not have leading or trailing whitespace")
            result.append((location, raw.strip()))

        if not result:
            self.error(Location(path, 1), "file contains no data records")
        return result

    def validate_airport(self, value: str, location: Location) -> bool:
        if not AIRPORT_RE.fullmatch(value):
            self.error(location, f"invalid ICAO airport code: {value!r}")
            return False
        return True

    def validate_runway(self, value: str, location: Location) -> bool:
        if not RUNWAY_RE.fullmatch(value):
            self.error(location, f"invalid runway designator: {value!r}")
            return False
        return True

    def runway_list(
        self, value: str, location: Location, field_name: str
    ) -> tuple[str, ...] | None:
        if value == "*":
            return None
        values = tuple(value.split(","))
        if not values or any(not item for item in values):
            self.error(location, f"{field_name} contains an empty runway")
            return tuple()
        if "*" in values:
            self.error(location, f"{field_name} must use * alone")
        for runway in values:
            self.validate_runway(runway, location)
        if len(values) != len(set(values)):
            self.error(location, f"{field_name} contains a duplicate runway")
        return values

    def validate_rate_file(self) -> None:
        seen_records: dict[str, Location] = {}
        seen_selectors: dict[tuple[object, ...], RateRule] = {}
        universal_seen: dict[str, Location] = {}

        for location, line in self.data_lines("rate.txt"):
            if line in seen_records:
                self.error(location, f"duplicate rule; first defined on line {seen_records[line].line}")
                continue
            seen_records[line] = location

            fields = line.split(":")
            if len(fields) != 9:
                self.error(location, f"rate rule must contain 9 colon-separated fields, found {len(fields)}")
                continue
            if any(field != field.strip() for field in fields):
                self.error(location, "fields must not contain surrounding whitespace")

            airport, a_marker, arr, not_arr, d_marker, dep, not_dep, dependent, rate_text = fields
            valid = self.validate_airport(airport, location)
            if a_marker != "A":
                self.error(location, "field 2 must be the literal A")
                valid = False
            if d_marker != "D":
                self.error(location, "field 5 must be the literal D")
                valid = False

            arrival = self.runway_list(arr, location, "arrival runway list")
            not_arrival = self.runway_list(not_arr, location, "excluded arrival runway list")
            departure = self.runway_list(dep, location, "departure runway list")
            not_departure = self.runway_list(not_dep, location, "excluded departure runway list")
            dependent_list = self.runway_list(dependent, location, "dependent runway list")

            if arrival and not_arrival:
                overlap = set(arrival) & set(not_arrival)
                if overlap:
                    self.error(location, f"arrival runway is both required and excluded: {', '.join(sorted(overlap))}")
            if departure and not_departure:
                overlap = set(departure) & set(not_departure)
                if overlap:
                    self.error(location, f"departure runway is both required and excluded: {', '.join(sorted(overlap))}")
            if departure and dependent_list:
                extra = set(dependent_list) - set(departure)
                if extra:
                    self.error(location, f"dependent runway is not in the departure list: {', '.join(sorted(extra))}")

            rates: list[tuple[int, int]] = []
            for pair in rate_text.split(","):
                parts = pair.split("_")
                if len(parts) != 2 or any(not part.isdigit() for part in parts):
                    self.error(location, f"invalid normal/LVO rate pair: {pair!r}")
                    valid = False
                    continue
                normal, lvo = map(int, parts)
                if normal <= 0 or lvo <= 0:
                    self.error(location, "normal and LVO rates must be greater than zero")
                    valid = False
                rates.append((normal, lvo))

            if departure and len(rates) not in (1, len(departure)):
                self.warning(
                    location,
                    "rate-pair count is neither one shared rate nor one rate per departure runway; confirm plugin mapping",
                )

            if not valid or not rates:
                continue
            rule = RateRule(
                location,
                airport,
                arrival,
                not_arrival,
                departure,
                not_departure,
                dependent_list,
                tuple(rates),
            )
            previous = seen_selectors.get(rule.selector)
            if previous:
                self.error(location, f"same runway selector already defined on line {previous.location.line}")
            else:
                seen_selectors[rule.selector] = rule

            if airport in universal_seen:
                self.error(
                    location,
                    f"rule is unreachable because a catch-all for {airport} appears on line {universal_seen[airport].line}",
                )
            if all(value is None for value in (arrival, not_arrival, departure, not_departure, dependent_list)):
                universal_seen[airport] = location
            self.rates.append(rule)

    def validate_sid_file(self) -> None:
        seen: dict[tuple[str, tuple[tuple[str, str], tuple[str, str]]], SidRule] = {}

        for location, line in self.data_lines("sidInterval.txt"):
            fields = line.split(",")
            if any(field != field.strip() for field in fields):
                self.error(location, "fields must not contain surrounding whitespace")
            if len(fields) == 5:
                airport, runway1, sid1, sid2, minutes_text = fields
                runway2 = runway1
            elif len(fields) == 6:
                airport, runway1, sid1, runway2, sid2, minutes_text = fields
            else:
                self.error(location, f"SID interval rule must contain 5 or 6 comma-separated fields, found {len(fields)}")
                continue

            valid = self.validate_airport(airport, location)
            valid = self.validate_runway(runway1, location) and valid
            valid = self.validate_runway(runway2, location) and valid
            for sid in (sid1, sid2):
                if not SID_RE.fullmatch(sid):
                    self.error(location, f"invalid SID point: {sid!r}")
                    valid = False
            try:
                minutes = Decimal(minutes_text)
                if not minutes.is_finite() or minutes <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.error(location, f"separation must be a positive number: {minutes_text!r}")
                valid = False
                minutes = Decimal(0)

            if not valid:
                continue
            rule = SidRule(location, airport, runway1, sid1, runway2, sid2, minutes)
            key = (airport, rule.pair)
            previous = seen.get(key)
            if previous:
                if previous.minutes == minutes:
                    self.error(location, f"duplicate SID pair; first defined on line {previous.location.line}")
                else:
                    self.error(
                        location,
                        f"conflicting SID separation ({previous.minutes} vs {minutes}); first defined on line {previous.location.line}",
                    )
            else:
                seen[key] = rule
            self.sid_rules.append(rule)

    @staticmethod
    def orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])

    @classmethod
    def proper_intersection(
        cls,
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
        d: tuple[float, float],
    ) -> bool:
        o1, o2 = cls.orientation(a, b, c), cls.orientation(a, b, d)
        o3, o4 = cls.orientation(c, d, a), cls.orientation(c, d, b)
        return o1 * o2 < 0 and o3 * o4 < 0

    def validate_taxi_file(self) -> None:
        seen: dict[tuple[object, ...], TaxiZone] = {}

        for location, line in self.data_lines("taxizones.txt"):
            fields = line.split(":")
            if len(fields) != 11:
                self.error(location, f"taxi-zone rule must contain 11 colon-separated fields, found {len(fields)}")
                continue
            if any(field != field.strip() for field in fields):
                self.error(location, "fields must not contain surrounding whitespace")

            airport, runway, *coordinate_and_time = fields
            valid = self.validate_airport(airport, location)
            valid = self.validate_runway(runway, location) and valid
            points: list[tuple[float, float]] = []
            for index in range(0, 8, 2):
                try:
                    latitude = float(coordinate_and_time[index])
                    longitude = float(coordinate_and_time[index + 1])
                except ValueError:
                    self.error(location, "latitude and longitude values must be numeric")
                    valid = False
                    continue
                if not math.isfinite(latitude) or not -90 <= latitude <= 90:
                    self.error(location, f"latitude is outside -90..90: {latitude}")
                    valid = False
                if not math.isfinite(longitude) or not -180 <= longitude <= 180:
                    self.error(location, f"longitude is outside -180..180: {longitude}")
                    valid = False
                points.append((latitude, longitude))

            minutes_text = coordinate_and_time[8]
            if not minutes_text.isdigit() or int(minutes_text) <= 0:
                self.error(location, f"taxi time must be a positive whole number: {minutes_text!r}")
                valid = False
                minutes = 0
            else:
                minutes = int(minutes_text)

            if len(points) == 4:
                if len(set(points)) != 4:
                    self.error(location, "taxi-zone polygon must contain four distinct points")
                    valid = False
                area = abs(
                    sum(
                        points[i][0] * points[(i + 1) % 4][1]
                        - points[(i + 1) % 4][0] * points[i][1]
                        for i in range(4)
                    )
                    / 2
                )
                if area == 0:
                    self.error(location, "taxi-zone polygon has zero area")
                    valid = False
                if self.proper_intersection(points[0], points[1], points[2], points[3]) or self.proper_intersection(
                    points[1], points[2], points[3], points[0]
                ):
                    self.error(location, "taxi-zone polygon crosses itself; check point order")
                    valid = False

            if not valid or len(points) != 4:
                continue
            zone = TaxiZone(location, airport, runway, tuple(points), minutes)
            key = (airport, runway, tuple(points))
            previous = seen.get(key)
            if previous:
                if previous.minutes == minutes:
                    self.error(location, f"duplicate taxi zone; first defined on line {previous.location.line}")
                else:
                    self.error(
                        location,
                        f"same taxi-zone polygon has conflicting times ({previous.minutes} vs {minutes}); first defined on line {previous.location.line}",
                    )
            else:
                seen[key] = zone
            self.taxi_zones.append(zone)

    def runway_is_covered(self, airport: str, runway: str) -> bool:
        for rule in self.rates:
            if rule.airport != airport:
                continue
            if rule.departure is None or runway in rule.departure:
                return True
        return False

    def validate_cross_file_logic(self) -> None:
        for rule in self.sid_rules:
            for runway in {rule.runway1, rule.runway2}:
                if not self.runway_is_covered(rule.airport, runway):
                    self.warning(
                        rule.location,
                        f"SID runway {rule.airport}/{runway} is not covered by any departure rate rule",
                    )
        for zone in self.taxi_zones:
            if not self.runway_is_covered(zone.airport, zone.runway):
                self.warning(
                    zone.location,
                    f"taxi-zone runway {zone.airport}/{zone.runway} is not covered by any departure rate rule",
                )

    def run(self) -> bool:
        self.validate_rate_file()
        self.validate_sid_file()
        self.validate_taxi_file()
        self.validate_cross_file_logic()
        print(f"Validation complete: {self.errors} error(s), {self.warnings} warning(s).")
        return self.errors == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root containing rate.txt, sidInterval.txt, and taxizones.txt",
    )
    parser.add_argument(
        "--no-annotations",
        action="store_true",
        help="print conventional file:line messages instead of GitHub annotations",
    )
    args = parser.parse_args(argv)
    validator = Validator(args.root.resolve(), annotations=not args.no_annotations)
    return 0 if validator.run() else 1


if __name__ == "__main__":
    sys.exit(main())
