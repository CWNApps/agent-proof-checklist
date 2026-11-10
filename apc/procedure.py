"""The rules (design section 6). Blocking view = every bound record; supporting view = qualifying records only (1.1)."""
from decimal import Decimal

from .dictionary import derived_parts, format_time, load_dictionary, parse_time, validate

ORDER = ["DISAGREES", "NOT_ACTIVE", "UNVERIFIABLE", "SELF_REPORT_ONLY", "NO_OUTSIDE_SOURCE", "NOT_CAPTURED"]
LINES = ["AP-1", "AP-2", "AP-3", "AP-4", "AP-5", "AP-6", "AP-7", "AP-8"]
LINE_PARTS = {"AP-1": ["AP-1.agent", "AP-1.person"], "AP-2": ["AP-2.request"], "AP-3": ["AP-3.limits"],
              "AP-4": ["AP-4.approval"], "AP-5": ["AP-5.attempts", "AP-5.related"],
              "AP-6": ["AP-6.charge", "AP-6.order", "AP-6.delivery"], "AP-7": ["AP-7.claim"]}
ANCHOR_KINDS = ("authorization", "payment_request", "attempt_log", "order")
PAYMENT_KINDS = ("payment_request", "authorization")
PERSON_PARTS = ("AP-1.person", "AP-2.request", "AP-3.limits", "AP-4.approval")
SIGNERS = {
    "AP-1.agent": {"network", "issuer", "psp", "merchant", "other"},
    "AP-1.person": {"person", "credentials_provider", "issuer"},
    "AP-2.request": {"person", "credentials_provider", "issuer"},
    "AP-3.limits": {"person", "credentials_provider", "issuer"},
    "AP-4.approval": {"person", "credentials_provider", "issuer", "wallet"},
    "AP-5.attempts": {"psp", "network", "issuer", "merchant"},
    "AP-5.related": {"psp", "network", "issuer", "merchant"},
    "AP-6.charge": {"psp", "network", "issuer"},
    "AP-6.order": {"merchant", "psp"},
    "AP-6.delivery": {"carrier", "merchant"},
}
DEFAULT_REVOKERS = ("issuer", "credentials_provider", "psp", "token_service")


class InvalidFiling(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def derive(filing: object) -> dict:
    if isinstance(filing, dict) and any(k in filing for k in ("action_time", "lines", "unbound_record_ids")):
        errs = validate(filing, filed=True)
        filing = {k: v for k, v in filing.items() if k not in ("action_time", "lines", "unbound_record_ids")}
    else:
        errs = validate(filing, filed=False)
    if errs:
        raise InvalidFiling(errs)
    return _Case(filing).output()


def _first(codes):
    codes = [c for c in codes if c in ORDER]
    return min(codes, key=ORDER.index) if codes else None


class _Case:
    def __init__(self, f):
        self.f = f
        self.recs = f["records"]
        self.by_id = {r["id"]: r for r in self.recs}
        self.cb = f["case_binding"]
        self.keepers = f["keepers"]
        self.kinds = load_dictionary()["kinds"]
        self.parts = {r["id"]: derived_parts(r) for r in self.recs}
        self.t = {r["id"]: parse_time(r["fields"][self.kinds[r["kind"]]["time_field"]]) for r in self.recs}
        self._bind()
        self._times()
        self._identities()
        self._aggregates()

    # ---- record facts -------------------------------------------------------------------------------------------
    @staticmethod
    def agent_side(r):
        return (r["party_role"] in ("agent", "agent_operator") or r["runs_agent"] != "false"
                or r["operator_affiliated"] != "false" or r["signer"] == "agent")

    def person_held(self, r):
        return not self.agent_side(r) and (r["party_role"] == "person" or r["signer"] == "person")

    def outside(self, r):
        return not self.agent_side(r) and not self.person_held(r)

    @staticmethod
    def checked(r):
        return r["check"] in ("verified_by_other", "recomputed")

    def fv(self, r, name):
        return r["fields"].get(name)

    # ---- 6.0 binding ---------------------------------------------------------------------------------------------
    def _bind(self):
        depth, supported = {}, set()
        for r in self.recs:
            b = r["binding"]
            if b["kind"] == self.cb["kind"] and b["value"] == self.cb["value"]:
                depth[r["id"]] = 0
                supported.add(r["id"])
        for d in (1, 2):
            for r in self.recs:
                if r["id"] in depth:
                    continue
                via = r["binding"]["via"]
                a = self.by_id.get(via) if via else None
                if a is None or depth.get(a["id"]) != d - 1 or a["kind"] not in ANCHOR_KINDS:
                    continue
                if r["binding"]["value"] not in (a["fields"].get("link_tokens") or []):
                    continue
                depth[r["id"]] = d
                if a["id"] in supported and self.outside(a) and self.checked(a):
                    supported.add(r["id"])
        bound = set(depth)
        for r in self.recs:
            if r["kind"] == "status" and r["fields"]["permission_of"] in bound:
                bound.add(r["id"])
        self.bound_ids, self.supported_ids = bound, supported
        self.bound = [r for r in self.recs if r["id"] in bound]

    def is_bound(self, r):
        return r["id"] in self.bound_ids

    def is_supported(self, r):
        return r["id"] in self.supported_ids

    def bound_kind(self, *kinds):
        return [r for r in self.bound if r["kind"] in kinds]

    # ---- 6.3 times -----------------------------------------------------------------------------------------------
    def _times(self):
        ts = [self.t[r["id"]] for r in self.bound_kind(*PAYMENT_KINDS)]
        ts += [parse_time(r["fields"]["first_request_at"]) for r in self.bound_kind("attempt_log")]
        self.action = min(ts) if ts else None
        self.last = max(ts) if ts else None
        # Supported last payment time (6.5): only payment records that QUALIFY for their own part count, so "an added
        # record that does not qualify cannot move this bound" holds (DERIVATION_LOG D-2). AP-5.attempts and
        # AP-6.charge qualification does not read sup_last, so there is no cycle.
        self.sup_last = None
        sup = [self.t[r["id"]] for r in self.bound_kind(*PAYMENT_KINDS)
               if self.base_qualifies(r, "AP-5.attempts" if r["kind"] == "payment_request" else "AP-6.charge")]
        self.sup_last = max(sup) if sup else None

    # ---- 6.0 / 6.4 / 6.5 qualification (without the line-specific tests) --------------------------------------
    def base_qualifies(self, r, part):
        if not self.is_supported(r) or part not in self.parts[r["id"]] or not self.checked(r):
            return False
        if self.agent_side(r):
            return False
        if self.person_held(r) and part not in PERSON_PARTS:
            return False
        if part in SIGNERS and r["signer"] not in SIGNERS[part]:
            return False
        if part == "AP-6.charge" and r["party_role"] not in ("psp", "network", "issuer"):
            return False
        t = self.t[r["id"]]
        if part == "AP-1.agent":
            if self.sup_last is None or t > self.sup_last:
                return False
        elif part in PERSON_PARTS:
            if self.action is None or not t < self.action:
                return False
        return True

    # ---- 6.6 identities ------------------------------------------------------------------------------------------
    def _identities(self):
        self.case_agent = {r["fields"]["agent_identity"] for r in self.recs
                           if r["kind"] == "identity" and self.base_qualifies(r, "AP-1.agent")}
        self.case_person = {r["fields"]["person_identity"] for r in self.recs
                            if r["kind"] == "mandate" and self.base_qualifies(r, "AP-1.person")
                            and r["fields"]["agent_identity"] in self.case_agent}
        agents = {r["fields"]["agent_identity"] for r in self.bound_kind("identity", "mandate", "token")
                  if "agent_identity" in r["fields"]}
        persons = {r["fields"]["person_identity"] for r in self.bound_kind("mandate", "approval")}
        self.identity_conflict = len(agents) > 1 or len(persons) > 1

    # ---- 6.7 aggregates (blocking view) --------------------------------------------------------------------------
    def _charges(self, recs):
        ch = {}
        for r in recs:
            if r["kind"] == "authorization":
                items = [{"charge_id": r["fields"]["charge_id"], "amount": r["fields"]["amount"],
                          "currency": r["fields"]["currency"]}]
            elif r["kind"] == "attempt_log":
                items = r["fields"]["charges"]
            else:
                continue
            for c in items:
                ch.setdefault(c["charge_id"], set()).add((Decimal(c["amount"]), c["currency"]))
        conflict = any(len(v) > 1 for v in ch.values())
        currencies = {cur for v in ch.values() for _, cur in v}
        total = None
        if ch and not conflict and len(currencies) == 1:
            total = sum(next(iter(v))[0] for v in ch.values())
        return ch, conflict, (next(iter(currencies)) if len(currencies) == 1 else None), total

    def _aggregates(self):
        self.charges, self.charge_conflict, self.cur, self.total = self._charges(self.bound)
        caps = self.bound_kind("mandate", "token")
        capped = [r for r in caps if "cap" in r["fields"]]
        self.cap = min((Decimal(r["fields"]["cap"]) for r in capped), default=None)
        capcur = {r["fields"].get("currency") for r in capped}
        self.cap_cur = next(iter(capcur)) if len(capcur) == 1 and None not in capcur else None
        self.cumulative = any(r["fields"].get("cap_scope") == "cumulative" for r in capped)
        lists = [set(r["fields"]["allowed_sellers"]) for r in caps if "allowed_sellers" in r["fields"]]
        self.allowed = set.intersection(*lists) if lists else None
        self.sellers = {r["fields"]["seller"] for r in self.bound_kind(*PAYMENT_KINDS)}
        self.orders = self.bound_kind("order")

    def approval_test(self, r):
        f = r["fields"]
        if self.total is None or self.cur is None or not self.orders:
            return False
        if Decimal(f["amount"]) < self.total or f["currency"] != self.cur:
            return False
        if f["person_identity"] not in self.case_person:
            return False
        for o in self.orders:
            if o["fields"]["item_id"] != f["item_id"]:
                return False
            if "quantity" in f and o["fields"]["quantity"] != f["quantity"]:
                return False
        return True

    def qualifies(self, r, part):
        if not self.base_qualifies(r, part):
            return False
        k, f = r["kind"], r["fields"]
        if k == "mandate" and part in ("AP-1.person", "AP-2.request", "AP-3.limits"):
            return f["agent_identity"] in self.case_agent
        if k == "token":
            return "agent_identity" not in f or f["agent_identity"] in self.case_agent
        if part == "AP-4.approval":
            return k == "approval" and self.approval_test(r)
        return True

    # ---- 6.11.3 part reasons --------------------------------------------------------------------------------------
    def part_reason(self, part, recs, qualifies):
        if any(r["check"] == "failed" for r in recs):
            return "UNVERIFIABLE"
        if any(qualifies(r) for r in recs):
            return "PRESENT"
        if any(self.outside(r) and r["check"] in ("not_run", "none") for r in recs):
            return "UNVERIFIABLE"
        if any(self.agent_side(r) or self.person_held(r) for r in recs):
            key = part.split(":")[0]
            return "NO_OUTSIDE_SOURCE" if self.keepers.get(key) == "none" else "SELF_REPORT_ONLY"
        return "NOT_CAPTURED"

    def with_part(self, part):
        return [r for r in self.bound if part in self.parts[r["id"]]]

    # ---- 6.11.1 material conflicts ---------------------------------------------------------------------------------
    def material_codes(self):
        out = {ln: set() for ln in LINES}
        mat = load_dictionary()["material_fields"]
        line_of = lambda r: {p.split(".")[0] for p in self.parts[r["id"]]}
        for i, a in enumerate(self.bound):
            for b in self.bound[i + 1:]:
                if a["kind"] != b["kind"]:
                    continue
                key = self.kinds[a["kind"]]["entity_key"]
                if key in (None, "@id") or a["fields"].get(key) != b["fields"].get(key):
                    continue
                for m in mat:
                    if m in a["fields"] and m in b["fields"] and _norm(m, a["fields"][m]) != _norm(m, b["fields"][m]):
                        for ln in line_of(a) & line_of(b):
                            out[ln].add("DISAGREES")
        sellers = {r["fields"]["seller"] for r in self.bound_kind("payment_request", "authorization", "order")
                   if "seller" in r["fields"]}
        if len(sellers) > 1:
            out["AP-6"].add("DISAGREES")
        curs = {r["fields"]["currency"] for r in self.bound_kind("payment_request", "authorization", "order")
                if "currency" in r["fields"]}
        curs |= {c["currency"] for r in self.bound_kind("attempt_log") for c in r["fields"]["charges"]}
        if len(curs) > 1:
            out["AP-6"].add("DISAGREES")
        holders = self.bound_kind("mandate", "approval", "order")
        for m in ("item_id", "quantity", "unit_price"):
            have = [r for r in holders if m in r["fields"]]
            for i, a in enumerate(have):
                for b in have[i + 1:]:
                    if _norm(m, a["fields"][m]) != _norm(m, b["fields"][m]):
                        ln = "AP-2" if "mandate" in (a["kind"], b["kind"]) else "AP-6"
                        out[ln].add("DISAGREES")
        return out

    def open_deliveries(self):
        dels = self.bound_kind("delivery")
        qual = [r for r in dels if self.qualifies(r, "AP-6.delivery")]
        return {r["fields"]["delivery_status"] for r in dels
                if not any(self.t[q["id"]] > self.t[r["id"]] for q in qual)}

    # ---- lines --------------------------------------------------------------------------------------------------
    def output(self):
        codes = self.material_codes()
        if self.identity_conflict:
            codes["AP-1"].add("DISAGREES")
        if self.charge_conflict:
            codes["AP-6"].add("DISAGREES")
        att = [r for r in self.recs if r["kind"] == "attempt_log" and self.qualifies(r, "AP-5.attempts")]
        if att:
            covered = {x for r in att for x in r["fields"]["request_ids"]}
            if any(r["fields"]["request_id"] not in covered for r in self.bound_kind("payment_request")):
                codes["AP-5"].add("DISAGREES")
        rel = [r for r in self.recs if self.qualifies(r, "AP-5.related")]
        if rel:
            listed = {c["charge_id"] for r in rel for c in r["fields"]["charges"]}
            if any(r["fields"]["charge_id"] not in listed for r in self.bound_kind("authorization")):
                codes["AP-5"].add("DISAGREES")
        lines = {}
        for ln in ("AP-1", "AP-2", "AP-3", "AP-5", "AP-6"):
            lines[ln] = self.generic_line(ln, codes[ln])
        lines["AP-7"] = self.ap7()
        lines["AP-8"] = self.ap8()
        lines["AP-4"] = self.ap4(lines)
        unbound = sorted(r["id"] for r in self.recs if r["id"] not in self.bound_ids)
        return {"action_time": format_time(self.action), "unbound_record_ids": unbound,
                "lines": [lines[ln] for ln in LINES]}

    def _line(self, ln, line_codes, parts):
        reasons = [p["reason"] for p in parts if p["reason"] != "PRESENT"]
        res = _first(list(line_codes) + reasons)
        return {"id": ln, "result": res or "PRESENT", "line_codes": sorted(line_codes), "parts": parts}

    def generic_line(self, ln, line_codes):
        parts = []
        for p in LINE_PARTS[ln]:
            recs = self.with_part(p)
            parts.append({"part": p, "reason": self.part_reason(p, recs, lambda r, p=p: self.qualifies(r, p)),
                          "record_ids": sorted(r["id"] for r in recs)})
        return self._line(ln, line_codes, parts)

    def ap7(self):
        claims = self.with_part("AP-7.claim")
        ids = sorted(r["id"] for r in claims)
        if not claims:
            return {"id": "AP-7", "result": "NOT_CAPTURED", "line_codes": [],
                    "parts": [{"part": "AP-7.claim", "reason": "NOT_CAPTURED", "record_ids": ids}]}
        sup = [r for r in self.recs if self.qualifies(r, "AP-6.charge") or self.qualifies(r, "AP-5.related")]
        _, _, _, sup_total = self._charges(sup)
        opened = self.open_deliveries()
        bad = False
        for c in claims:
            f = c["fields"]
            if "delivery_status" in f and (not opened or any(s != f["delivery_status"] for s in opened)):
                bad = True
            for m in ("item_id", "quantity"):
                if m in f and (not self.orders or any(_norm(m, o["fields"][m]) != _norm(m, f[m]) for o in self.orders)):
                    bad = True
            if "amount" in f and (self.total is None or sup_total is None or Decimal(f["amount"]) != self.total
                                  or Decimal(f["amount"]) != sup_total):
                bad = True
            if "currency" in f and (self.cur is None or f["currency"] != self.cur):
                bad = True
            if "seller" in f and (not self.sellers or any(s != f["seller"] for s in self.sellers)):
                bad = True
        res = "DISAGREES" if bad else "PRESENT"
        return {"id": "AP-7", "result": res, "line_codes": ["DISAGREES"] if bad else [],
                "parts": [{"part": "AP-7.claim", "reason": res, "record_ids": ids}]}

    # ---- 6.9 AP-8 -----------------------------------------------------------------------------------------------
    def revokers(self, p):
        return set(p["fields"].get("revocable_by") or DEFAULT_REVOKERS)

    def inactive(self, p):
        if self.action is None:
            return False
        f = p["fields"]
        for s in self.bound_kind("status"):
            sf = s["fields"]
            if sf["permission_of"] == p["id"] and sf["permission_status"] != "active" \
                    and parse_time(sf["effective_at"]) <= self.last:
                return True
        if "expires_at" in f and parse_time(f["expires_at"]) <= self.last:
            return True
        if "not_before" in f and parse_time(f["not_before"]) > self.action:
            return True
        return False

    def active_evidence(self, s, p):
        if self.action is None:
            return False
        sf = s["fields"]
        if not (self.is_supported(s) and self.outside(s) and self.checked(s) and s["party_role"] in self.revokers(p)
                and sf["permission_of"] == p["id"]):
            return False
        if "active_since" not in sf or parse_time(sf["active_since"]) > self.action:
            return False
        if sf["permission_status"] == "active":
            return parse_time(sf["status_as_of"]) >= self.last
        return parse_time(sf["effective_at"]) > self.last

    def ap8(self):
        perms = sorted(self.bound_kind("mandate", "token"), key=lambda r: r["id"])
        parts = []
        for p in perms:
            key = f"AP-8.status:{p['id']}"
            recs = [s for s in self.bound_kind("status") if s["fields"]["permission_of"] == p["id"]]
            if self.inactive(p):
                reason = "NOT_ACTIVE"
            else:
                reason = self.part_reason(key, recs, lambda s, p=p: self.active_evidence(s, p))
            parts.append({"part": key, "reason": reason, "record_ids": sorted(s["id"] for s in recs)})
        if not perms:
            recs = self.bound_kind("status")
            reason = self.part_reason("AP-8.status", recs, lambda s: False)
            parts.append({"part": "AP-8.status", "reason": reason, "record_ids": sorted(s["id"] for s in recs)})
        return self._line("AP-8", set(), parts)

    # ---- 6.8 AP-4 -----------------------------------------------------------------------------------------------
    def not_required(self, lines):
        if any(lines[ln]["result"] != "PRESENT" for ln in ("AP-1", "AP-2", "AP-3", "AP-5", "AP-6", "AP-8")):
            return False
        if self.total is None or self.cap is None or self.cumulative or self.cap_cur != self.cur or self.total > self.cap:
            return False
        if self.allowed is not None and (not self.sellers or not self.sellers <= self.allowed):
            return False
        if not self.orders or not any("AP-2.request" in self.parts[m["id"]] for m in self.bound_kind("mandate")):
            return False
        holders = self.bound_kind("mandate", "approval", "order")
        for m in ("item_id", "quantity", "unit_price"):
            if len({_norm(m, r["fields"][m]) for r in holders if m in r["fields"]}) > 1:
                return False
        return True

    def ap4(self, lines):
        recs = self.with_part("AP-4.approval")
        ids = sorted(r["id"] for r in recs)
        if self.not_required(lines):
            return {"id": "AP-4", "result": "NOT_REQUIRED", "line_codes": [],
                    "parts": [{"part": "AP-4.approval", "reason": "NOT_REQUIRED", "record_ids": ids}]}
        reason = self.part_reason("AP-4.approval", recs, lambda r: self.qualifies(r, "AP-4.approval"))
        return self._line("AP-4", set(), [{"part": "AP-4.approval", "reason": reason, "record_ids": ids}])


def _norm(name, v):
    if name in ("amount", "unit_price", "cap"):
        return Decimal(v)
    if name == "quantity":
        return int(v)
    return v
