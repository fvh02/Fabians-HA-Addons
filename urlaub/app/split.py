"""Who pays for what.

Every person has yes/no answers for the trip's categories (Alkohol, Bier, Vodka …). An item with
categories is shared by the people who said yes to all of them – beer only by beer drinkers. A
category with a parent (Bier → Alkohol) also needs a yes for the parent: whoever doesn't drink
alcohol pays no beer, even if "Bier" was never answered. Unanswered counts as yes. Items without
categories are shared by everyone; a hand-picked list of people always wins.
"""

from collections import defaultdict

CENT = 100


def says_yes(member: dict, tag_id: str, tags: dict[str, dict]) -> bool:
    answers = member.get("answers") or {}
    seen = set()
    while tag_id and tag_id not in seen:
        seen.add(tag_id)
        if answers.get(tag_id) is False:
            return False
        tag = tags.get(tag_id)
        tag_id = tag.get("parent") if tag else None
    return True


def consumers(item: dict, members: list[dict], tags: dict[str, dict]) -> list[str]:
    """Ids of the people who share an item."""
    if item.get("people"):
        chosen = [m["id"] for m in members if m["id"] in item["people"]]
        if chosen:
            return chosen
    want = [t for t in item.get("tags") or [] if t in tags]
    people = [m["id"] for m in members if all(says_yes(m, t, tags) for t in want)]
    return people or [m["id"] for m in members]       # nobody matches: share among all


def shares(amount_cents: int, people: list[str]) -> dict[str, int]:
    """Split an amount in cents exactly (the first ones pay the leftover cents)."""
    if not people:
        return {}
    base, rest = divmod(amount_cents, len(people))
    return {p: base + (1 if i < rest else 0) for i, p in enumerate(sorted(people))}


def balances(members: list[dict], tags: dict[str, dict], receipts: list[dict]) -> dict:
    """Paid, owed and the net balance per person (cents), plus the share of every item."""
    paid, owed = defaultdict(int), defaultdict(int)
    per_item = {}
    for receipt in receipts:
        payer = receipt.get("payer")
        total = 0
        for item in receipt["items"]:
            cents = round(item["price"] * CENT)
            people = consumers(item, members, tags)
            per_item[item["id"]] = people
            for p, c in shares(cents, people).items():
                owed[p] += c
            total += cents
        if payer:
            paid[payer] += total
    ids = [m["id"] for m in members]
    return {"paid": {i: paid[i] for i in ids}, "owed": {i: owed[i] for i in ids},
            "net": {i: paid[i] - owed[i] for i in ids}, "items": per_item}


def settle(net: dict[str, int]) -> list[dict]:
    """Few transfers that even everything out: the biggest debtor pays the biggest creditor."""
    debtors = sorted(((-v, k) for k, v in net.items() if v < 0), reverse=True)
    creditors = sorted(((v, k) for k, v in net.items() if v > 0), reverse=True)
    out = []
    d = c = 0
    while d < len(debtors) and c < len(creditors):
        owe, who = debtors[d]
        get, whom = creditors[c]
        amount = min(owe, get)
        if amount > 0:
            out.append({"from": who, "to": whom, "cents": amount})
        debtors[d] = (owe - amount, who)
        creditors[c] = (get - amount, whom)
        if debtors[d][0] == 0:
            d += 1
        if creditors[c][0] == 0:
            c += 1
    return out
