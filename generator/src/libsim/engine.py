"""Day-by-day simulation of an online library.

Every member carries a hidden satisfaction state s (AR(1) towards a personal baseline,
pushed by events: good/bad reads, lapsed holds, searches with no results). s drives activity
and — together with tenure, frustrations and inactivity — churn, which happens only when a
paid period ends. A randomized retention campaign in the past assigns e-mails/discounts with
heterogeneous true effects. The simulation runs `horizon_days` past `as_of`; that future is
never written to the dataset, only to ground truth (outcomes under every action, drawn with
common random numbers).

Times are stored as local seconds since the start date and converted to UTC by the writer.
"""

import bisect
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from libsim.catalog.genres import GENRES
from libsim.params import EDUCATION, PLANS, Params
from libsim.population import Population, base_genre_share, make_population
from libsim.world import GENRE_CODES, Books, load_books, load_calibration

FREE, TRIAL, PAID, CHURNED, PENDING = 1, 2, 3, 4, 0
LOAN_LIMIT = {FREE: 1, TRIAL: 3, PAID: 3, CHURNED: 0, PENDING: 0}
ACTIVITY_BY_STATUS = {FREE: 0.55, TRIAL: 1.0, PAID: 1.0, CHURNED: 0.0, PENDING: 0.0}
PLAN_CODES = list(PLANS)
ACTIONS = ("none", "email", "discount")

# Local hour-of-day profiles by chronotype (morning, evening, night owl).
_HOURS = np.arange(24)
_PROFILES = np.array(
    [
        np.exp(-((_HOURS - 7.5) ** 2) / 4)
        + 0.6 * np.exp(-((_HOURS - 12.5) ** 2) / 2)
        + 0.5 * np.exp(-((_HOURS - 20) ** 2) / 4),
        0.3 * np.exp(-((_HOURS - 8) ** 2) / 3)
        + 0.4 * np.exp(-((_HOURS - 13) ** 2) / 3)
        + np.exp(-((_HOURS - 21) ** 2) / 5),
        0.3 * np.exp(-((_HOURS - 14) ** 2) / 6) + np.exp(-((((_HOURS + 12) % 24) - 12.5) ** 2) / 6),
    ]
)
HOUR_PROFILES = _PROFILES / _PROFILES.sum(axis=1, keepdims=True)
HOUR_CDF = np.cumsum(HOUR_PROFILES, axis=1)
ACTIVITY = np.array([ACTIVITY_BY_STATUS[s] for s in range(5)])
LIMIT = np.array([LOAN_LIMIT[s] for s in range(5)])


@dataclass
class Event:
    """Row buffers (lists) for every output table."""

    subscription_periods: list[list] = field(default_factory=list)
    loans: list[list] = field(default_factory=list)
    reading_sessions: list[list] = field(default_factory=list)
    searches: list[list] = field(default_factory=list)
    holds: list[list] = field(default_factory=list)
    campaign_assignments: list[list] = field(default_factory=list)


@dataclass
class Result:
    params: Params
    start: date
    observed_days: int
    books: Books
    population: Population
    events: Event
    campaign: dict
    ground_truth: dict


class Simulation:
    def __init__(self, params: Params) -> None:
        self.p = params
        streams = np.random.SeedSequence(params.seed).spawn(5)
        rng_books, rng_pop, rng_daily, rng_campaign, rng_outcome = map(
            np.random.default_rng, streams
        )
        self.rng, self.rng_campaign, self.rng_outcome = rng_daily, rng_campaign, rng_outcome

        self.start = params.as_of - timedelta(days=round(params.months * 30.4375))
        self.observed_days = (params.as_of - self.start).days + 1  # days 0..observed_days-1
        self.total_days = self.observed_days + params.horizon_days
        calibration = load_calibration()
        self.books = load_books(params, rng_books)
        self.pop = make_population(params, self.observed_days, calibration, rng_pop)
        self.base_share = base_genre_share(calibration)
        self.ev = Event()
        self._init_choice_tables()
        self._init_state()

        es = params.effect_scale
        ch, tr = params.churn, params.treatment
        self.beta = {
            "satisfaction": ch.satisfaction * es,
            "frustrations_30d": ch.frustrations_30d * es,
            "log_tenure_months": ch.log_tenure_months * es,
            "inactivity_14d": ch.inactivity_14d * es,
            "hidden_factor": ch.hidden_factor * es,
        }
        self.tau_scale = es
        self.campaign_end = (
            self.observed_days - 1 - round(params.campaign.ends_months_before_as_of * 30.4375)
        )
        # Clipped to the observed history; a short simulation may have no campaign at all.
        self.campaign_start = max(0, self.campaign_end - round(params.campaign.months * 30.4375))
        self.avg_tau = self._average_effects() if not tr.heterogeneous else None
        self.ground_truth_risk: list[dict] = []
        self.ground_truth_campaign: list[dict] = []

    # ------------------------------------------------------------------ setup

    def _init_choice_tables(self) -> None:
        """Per (genre, uk_only) cumulative choice probabilities: popularity × quality."""
        b = self.books
        score = b.weight * np.exp(0.4 * b.quality)
        self.choice: dict[tuple[int, bool], tuple[np.ndarray, np.ndarray]] = {}
        for g in range(len(GENRE_CODES)):
            for uk_only in (False, True):
                mask = (b.genre == g) & ((b.language == 0) | (not uk_only))
                idx = np.flatnonzero(mask)
                if idx.size:
                    w = score[idx] * np.where(b.language[idx] == 0, 1.0, 0.85)
                    self.choice[(g, uk_only)] = (idx, np.cumsum(w) / w.sum())
        self.taste_cdf = np.cumsum(self.pop.taste, axis=1)

    def _init_state(self) -> None:
        n, nb = self.pop.n, self.books.n
        self.status = np.full(n, PENDING, dtype=np.int8)
        self.s = self.pop.baseline_s.copy()
        self.plan = np.full(n, -1, dtype=np.int8)
        self.period_end = np.full(n, -1)
        self.period_row = np.full(n, -1)
        self.trial_end = np.full(n, -1)
        self.tenure_start = np.full(n, -1)
        self.last_session = np.full(n, -(10**6))
        self.assigned = np.zeros(n, dtype=bool)
        self.pending_discount = np.zeros(n)
        self.session_days: list[deque[int]] = [deque() for _ in range(n)]
        self.frustrations: list[deque[int]] = [deque() for _ in range(n)]
        self.active_loans: list[list[int]] = [[] for _ in range(n)]
        self.open_holds = np.zeros(n, dtype=int)
        self.read: list[set[int]] = [set() for _ in range(n)]
        self.rating_bias = self.rng.normal(0.0, 0.35, n)
        self.out = np.zeros(nb, dtype=int)
        self.released_at = np.full(nb, -1)  # latest copy return time (keeps loan times sequential)
        # per book: open hold ids kept sorted by placement time (first come, first served)
        self.hold_queue: dict[int, list[int]] = defaultdict(list)
        # loan state: [user, book, start_t, due_day, pages_read, target_pages, will_complete]
        self.loan_state: list[list] = []
        self.attempts = np.zeros((2, nb), dtype=int)  # observed last 90 days / future window

    # ------------------------------------------------------------------ helpers

    def _t(self, day: int, user: int) -> int:
        hour = min(int(np.searchsorted(HOUR_CDF[self.pop.chronotype[user]], self.rng.random())), 23)
        return day * 86400 + int(hour) * 3600 + int(self.rng.integers(0, 3600))

    def _day_factor(self, day: int) -> np.ndarray:
        d = self.start + timedelta(days=day)
        f = 1.25 if d.weekday() >= 5 else 1.0
        if d.month in (6, 7, 8):
            f *= 0.85
        factor = np.full(self.pop.n, f)
        if d.month == 9:  # back to studies
            factor[self.pop.education == EDUCATION.index("student")] *= 1.25
        return factor

    def _fit(self, user: int, book: int) -> float:
        g = self.books.genre[book]
        return float(np.clip(np.log(self.pop.taste[user, g] / self.base_share[g]), -2.0, 2.0))

    def _frustrate(self, user: int, day: int, shock: float) -> None:
        self.s[user] += shock * self.p.effect_scale
        self.frustrations[user].append(day)

    def _count_recent(self, days: deque[int], today: int, window: int) -> int:
        while days and days[0] <= today - 90:
            days.popleft()
        return sum(1 for d in days if d > today - window)

    def _observed(self, day: int) -> bool:
        return day < self.observed_days

    # ------------------------------------------------------------------ run

    def run(self) -> Result:
        for day in range(self.total_days):
            self._registrations(day)
            self._satisfaction_drift(day)
            act = self._day_factor(day) * np.exp(self.p.activity_gamma * self.s)
            act *= ACTIVITY[self.status]
            self._expire_holds(day)
            self._return_overdue(day)
            self._reading(day, act)
            self._borrowing(day, act)
            self._browsing(day, act)
            self._trial_ends(day)
            self._free_upgrades(day)
            self._renewals(day)
        return Result(
            params=self.p,
            start=self.start,
            observed_days=self.observed_days,
            books=self.books,
            population=self.pop,
            events=self.ev,
            campaign={"start_day": self.campaign_start, "end_day": self.campaign_end},
            ground_truth=self._ground_truth(),
        )

    def _registrations(self, day: int) -> None:
        for u in np.flatnonzero(self.pop.registered_day == day):
            if self.pop.starts_trial[u]:
                self.status[u] = TRIAL
                self.trial_end[u] = day + self.p.trial_days
                self.period_row[u] = self._open_period(
                    int(u), "trial", day, day + self.p.trial_days, 0.0, 0.0
                )
            else:
                self.status[u] = FREE

    def _satisfaction_drift(self, day: int) -> None:
        live = (self.status == FREE) | (self.status == TRIAL) | (self.status == PAID)
        rho, p = self.p.s_persistence, self.p
        drift = (
            rho * self.s
            + (1 - rho) * self.pop.baseline_s
            + self.rng.normal(0.0, p.s_noise, self.pop.n)
        )
        self.s = np.where(live, drift, self.s)

    # ------------------------------------------------------------------ reading & loans

    def _reading(self, day: int, act: np.ndarray) -> None:
        holders = np.flatnonzero([bool(loans) for loans in self.active_loans])
        if holders.size == 0:
            return
        p_read = 1.0 - np.exp(-self.pop.session_rate[holders] * act[holders])
        for u in holders[self.rng.random(holders.size) < p_read]:
            loan = self.active_loans[u][0]
            state = self.loan_state[loan]
            minutes = int(
                np.clip(self.rng.lognormal(np.log(self.p.session_minutes_median), 0.55), 5, 180)
            )
            pages = max(1, round(minutes * self.pop.speed[u] * self.rng.uniform(0.8, 1.2)))
            pages = min(pages, state[5] - state[4])
            state[4] += pages
            device = self.pop.device[u] if self.rng.random() < 0.75 else self.rng.integers(0, 5)
            t = max(self._t(day, u), state[2] + 300)  # never before the loan started
            if self._observed(day):
                self.ev.reading_sessions.append(
                    [int(u), int(state[1]), t, minutes, int(pages), int(device)]
                )
            self.last_session[u] = day
            self.session_days[u].append(day)
            if state[4] >= state[5]:
                self._finish_loan(loan, day, t + minutes * 60, completed=bool(state[6]))

    def _finish_loan(self, loan: int, day: int, t: int, *, completed: bool) -> None:
        user, book = self.loan_state[loan][0], self.loan_state[loan][1]
        self.active_loans[user].remove(loan)
        q, fit = self.books.quality[book], self._fit(user, book)
        latent = 3.9 + 0.45 * q + 0.35 * fit + self.rating_bias[user] + self.rng.normal(0, 0.6)
        if not completed:
            latent -= 0.8
        rating = int(np.clip(np.rint(latent), 1, 5))
        rated = self.rng.random() < (0.25 + 0.15 * abs(latent - 3.5)) * (1.0 if completed else 0.6)
        good = completed and rating >= 4
        self.s[user] += (
            self.p.shock_good_read if good else self.p.shock_bad_read if rating <= 2 else 0.0
        ) * self.p.effect_scale
        row = self.ev.loans[loan]  # loan ids index both loan_state and the loans table
        row[3], row[4], row[5] = t, completed, (rating if rated else None)
        self._release_copy(book, day, t)

    def _return_overdue(self, day: int) -> None:
        for u in range(self.pop.n):
            for loan in list(self.active_loans[u]):
                if self.loan_state[loan][3] <= day:
                    self._finish_loan(loan, day, day * 86400 + 6 * 3600, completed=False)

    def _release_copy(self, book: int, day: int, t: int) -> None:
        self.out[book] -= 1
        self.released_at[book] = max(int(self.released_at[book]), t)
        queue = self.hold_queue[book]
        while queue:
            hold = queue.pop(0)
            user = self.ev.holds[hold][0]
            self.open_holds[user] -= 1
            if self.status[user] in (CHURNED, PENDING):
                self.ev.holds[hold][3:5] = [t, "cancelled"]
                continue
            self.ev.holds[hold][3:5] = [t, "fulfilled"]
            self._start_loan(user, book, day, via_hold=True)
            return

    def _start_loan(self, user: int, book: int, day: int, *, via_hold: bool) -> None:
        q, fit = self.books.quality[book], self._fit(user, book)
        p_complete = 1 / (
            1 + np.exp(-(1.2 + 0.6 * q + 0.7 * fit - 0.5 * np.log(self.books.pages[book] / 300)))
        )
        complete = self.rng.random() < p_complete
        target = (
            self.books.pages[book]
            if complete
            else max(1, int(self.books.pages[book] * self.rng.uniform(0.1, 0.6)))
        )
        t = max(self._t(day, user), int(self.released_at[book]) + 60)  # a copy must be back first
        loan = len(self.loan_state)
        self.loan_state.append([user, book, t, day + self.p.loan_days, 0, target, complete])
        self.ev.loans.append(
            [int(user), int(book), t, None, None, None, via_hold]
        )  # returned/completed/rating set on finish
        self.active_loans[user].append(loan)
        self.read[user].add(book)
        self.out[book] += 1

    def _expire_holds(self, day: int) -> None:
        for queue in self.hold_queue.values():
            while queue and self.ev.holds[queue[0]][2] <= (day - self.p.hold_days) * 86400:
                hold = queue.pop(0)
                user = self.ev.holds[hold][0]
                self.open_holds[user] -= 1
                self.ev.holds[hold][3:5] = [day * 86400 + 8 * 3600, "lapsed"]
                self._frustrate(user, day, self.p.shock_hold_lapsed)

    def _choose_book(self, user: int) -> int | None:
        uk_only = bool(self.pop.uk_only[user])
        for _ in range(4):
            g = int(
                np.searchsorted(self.taste_cdf[user], self.rng.random() * self.taste_cdf[user, -1])
            )
            table = self.choice.get((min(g, len(GENRE_CODES) - 1), uk_only))
            if table is None:
                continue
            idx, cdf = table
            book = int(idx[min(np.searchsorted(cdf, self.rng.random()), idx.size - 1)])
            if book not in self.read[user]:
                return book
        return None

    def _borrowing(self, day: int, act: np.ndarray) -> None:
        limit = LIMIT[self.status]
        busy = np.array([len(x) for x in self.active_loans]) + self.open_holds
        free_slot = np.flatnonzero(busy < limit)
        if free_slot.size == 0:
            return
        p = 1.0 - np.exp(
            -self.pop.reading_rate[free_slot] * act[free_slot] * (1.0 + (busy[free_slot] == 0))
        )
        for u in free_slot[self.rng.random(free_slot.size) < p]:
            self._borrow_intent(int(u), day)

    def _borrow_intent(self, user: int, day: int) -> None:
        book = self._choose_book(user)
        if book is None:
            return
        window = 0 if self._observed(day) else 1
        if not self._observed(day) or day >= self.observed_days - 90:
            self.attempts[window, book] += 1
        b = self.books
        if not b.in_library[book]:
            if self.rng.random() < self.p.search_missing_prob:
                self._search(user, day, book, results=0)
                self._frustrate(user, day, self.p.shock_zero_result)
            book = self._choose_book(user)  # substitute
            if book is None or not b.in_library[book]:
                return
        if self.rng.random() < 0.6:
            self._search(user, day, book, results=int(self.rng.integers(1, 40)))
        if self.out[book] < b.copies[book]:
            self._start_loan(user, book, day, via_hold=False)
            return
        choice = self.rng.choice(3, p=self.p.hold_choice)
        if choice == 0:
            hold = len(self.ev.holds)
            self.ev.holds.append([int(user), int(book), self._t(day, user), None, None])
            bisect.insort(self.hold_queue[book], hold, key=lambda h: self.ev.holds[h][2])
            self.open_holds[user] += 1
        elif choice == 1:
            alt = self._choose_book(user)
            if alt is not None and b.in_library[alt] and self.out[alt] < b.copies[alt]:
                self._start_loan(user, alt, day, via_hold=False)

    def _search(self, user: int, day: int, book: int, *, results: int) -> None:
        if not self._observed(day):
            return
        b = self.books
        query = b.title[book] if self.rng.random() < 0.7 else b.authors[book].split(", ")[0]
        self.ev.searches.append([int(user), self._t(day, user), query, int(results)])

    def _browsing(self, day: int, act: np.ndarray) -> None:
        if not self._observed(day):
            return
        users = np.flatnonzero(self.rng.random(self.pop.n) < 0.03 * act)
        for u in users:
            g = int(np.searchsorted(self.taste_cdf[u], self.rng.random() * self.taste_cdf[u, -1]))
            label = GENRES[GENRE_CODES[min(g, len(GENRE_CODES) - 1)]]
            self.ev.searches.append(
                [int(u), self._t(day, int(u)), label, int(self.rng.integers(20, 400))]
            )

    # ------------------------------------------------------------------ subscriptions

    def _open_period(
        self, user: int, plan: str, start: int, end: int, price: float, paid: float
    ) -> int:
        row = len(self.ev.subscription_periods)
        self.ev.subscription_periods.append(
            [int(user), plan, start * 86400, end * 86400, price, paid, None, "open"]
        )
        return row

    def _start_paid(self, user: int, day: int) -> None:
        young = self.pop.age[user] <= 1
        student = self.pop.education[user] == EDUCATION.index("student")
        if young and student and self.rng.random() < 0.8:
            plan = "student"
        else:
            plan = "annual" if self.rng.random() < 0.28 else "monthly"
        self.plan[user] = PLAN_CODES.index(plan)
        self.status[user] = PAID
        self.tenure_start[user] = day
        days = PLANS[plan]["days"]
        self.period_end[user] = day + days
        price = PLANS[plan]["price"]
        self.period_row[user] = self._open_period(user, plan, day, day + days, price, price)

    def _trial_ends(self, day: int) -> None:
        for u in np.flatnonzero((self.status == TRIAL) & (self.trial_end == day)):
            sessions = self._count_recent(self.session_days[u], day, self.p.trial_days)
            logit = self.p.trial_conversion_intercept + 1.0 * self.s[u] + 0.8 * (sessions >= 3)
            row = self.ev.subscription_periods[self.period_row[u]]
            if self.rng.random() < 1 / (1 + np.exp(-logit)):
                row[7] = "converted"
                self._start_paid(int(u), day)
            else:
                row[7] = "expired"
                self.status[u] = FREE

    def _free_upgrades(self, day: int) -> None:
        free = np.flatnonzero(self.status == FREE)
        p = 0.0008 * np.exp(self.s[free])
        for u in free[self.rng.random(free.size) < p]:
            self._start_paid(int(u), day)

    def _features(self, user: int, day: int) -> dict[str, float]:
        tenure_months = (day - self.tenure_start[user]) / 30.4375
        return {
            "satisfaction": float(self.s[user]),
            "frustrations_30d": self._count_recent(self.frustrations[user], day, 30),
            "log_tenure_months": float(np.log1p(tenure_months)),
            "inactivity_14d": float(self.last_session[user] < day - 14),
            "hidden_factor": float(self.pop.hidden_factor[user]),
        }

    def _tau(self, user: int, day: int, action: str) -> float:
        """True effect of an action on the churn logit for this user right now."""
        tr = self.p.treatment
        if action == "none":
            return 0.0
        if self.avg_tau is not None:
            return self.avg_tau[action]
        if action == "discount":
            lost = self.s[user] < tr.lost_cause_satisfaction
            return (
                0.0
                if lost
                else tr.discount_kappa * float(self.pop.price_sensitivity[user]) * self.tau_scale
            )
        if not self.pop.email_opt_in[user]:
            return 0.0
        recent = self._count_recent(self.session_days[user], day, 30)
        before = sum(1 for d in self.session_days[user] if day - 90 < d <= day - 30) / 2
        if self.last_session[user] < day - 30:
            return tr.email_dormant * self.tau_scale
        if recent < before:
            return tr.email_declining * self.tau_scale
        return tr.email_other * self.tau_scale

    def _average_effects(self) -> dict[str, float]:
        tr, es = self.p.treatment, self.p.effect_scale
        mean_ps = float(self.pop.price_sensitivity.mean())
        return {
            "discount": tr.discount_kappa * mean_ps * es * 0.85,
            "email": (0.35 * tr.email_declining + 0.15 * tr.email_dormant + 0.5 * tr.email_other)
            * self.p.email_opt_in
            * es,
        }

    def _churn_probability(self, user: int, day: int, action: str) -> float:
        plan = PLAN_CODES[self.plan[user]]
        x = self._features(user, day)
        logit = self.p.churn.intercept[plan] + sum(self.beta[k] * v for k, v in x.items())
        logit += self._tau(user, day, action)
        return float(1 / (1 + np.exp(-logit)))

    def _renewals(self, day: int) -> None:
        for u in np.flatnonzero((self.status == PAID) & (self.period_end == day)):
            u = int(u)
            row = self.ev.subscription_periods[self.period_row[u]]
            if not self._observed(day):
                self._future_renewal(u, day, row)
                continue
            action = "none"
            if self.campaign_start <= day <= self.campaign_end and not self.assigned[u]:
                action = self._assign(u, day)
            churned = self.rng.random() < self._churn_probability(u, day, action)
            self._settle(
                u,
                day,
                row,
                churned,
                discount=self.p.treatment.discount_pct if action == "discount" else 0.0,
            )

    def _assign(self, user: int, day: int) -> str:
        arms = self.p.campaign.arms
        arm = str(self.rng_campaign.choice(list(arms), p=list(arms.values())))
        self.assigned[user] = True
        delivered = arm == "discount" or (arm == "email" and bool(self.pop.email_opt_in[user]))
        sent = max(day - 7, 0)
        discount = self.p.treatment.discount_pct if arm == "discount" else 0.0
        self.ev.campaign_assignments.append(
            [
                int(user),
                sent * 86400 + 10 * 3600,
                arm,
                bool(delivered),
                float(discount),
                day * 86400,
            ]
        )
        received = arm if delivered else "none"
        self.ground_truth_campaign.append(
            {
                "user": user,
                "arm": arm,
                "received": received,
                "tau": {a: round(self._tau(user, day, a), 6) for a in ACTIONS},
                "p_true": {a: round(self._churn_probability(user, day, a), 6) for a in ACTIONS},
            }
        )
        return received

    def _settle(self, user: int, day: int, row: list, churned: bool, *, discount: float) -> None:
        if churned:
            row[7] = "churned"
            self.status[user] = CHURNED
            for loan in list(self.active_loans[user]):  # returned at the end of the last day
                end = max(day * 86400 + 86340, self.loan_state[loan][2] + 60)
                self._finish_loan(loan, day, end, completed=False)
            return
        row[7] = "renewed"
        plan = PLAN_CODES[self.plan[user]]
        days, price = PLANS[plan]["days"], PLANS[plan]["price"]
        self.period_end[user] = day + days
        self.period_row[user] = self._open_period(
            user, plan, day, day + days, price, round(price * (1 - discount), 2)
        )
        if discount:
            self.ev.subscription_periods[self.period_row[user]][6] = discount

    def _future_renewal(self, user: int, day: int, row: list) -> None:
        """After as_of: record outcomes under every action (common random number), act as 'none'."""
        u_draw = self.rng_outcome.random()
        p = {a: self._churn_probability(user, day, a) for a in ACTIONS}
        y = {a: bool(u_draw < p[a]) for a in ACTIONS}
        self.ground_truth_risk.append(
            {
                "user": user,
                "period_end_day": day,
                "plan": PLAN_CODES[self.plan[user]],
                "p_true": {a: round(v, 6) for a, v in p.items()},
                "outcome": y,
                "features": {k: round(v, 6) for k, v in self._features(user, day).items()},
            }
        )
        self._settle(user, day, row, y["none"], discount=0.0)

    # ------------------------------------------------------------------ ground truth

    def _ground_truth(self) -> dict:
        b, pop = self.books, self.pop
        months_observed = 3.0
        return {
            "params": self.p.to_dict(),
            "churn_logit": {"intercept": self.p.churn.intercept, "beta": self.beta},
            "users": {
                "satisfaction_as_of": self.s.round(6).tolist(),
                "baseline_satisfaction": pop.baseline_s.round(6).tolist(),
                "price_sensitivity": pop.price_sensitivity.round(6).tolist(),
                "hidden_factor": pop.hidden_factor.round(6).tolist(),
                "taste": pop.taste.round(6).tolist(),
            },
            "at_risk": self.ground_truth_risk,
            "campaign": self.ground_truth_campaign,
            "books": {"quality": b.quality.round(6).tolist(), "weight": b.weight.round(6).tolist()},
            "candidates": {
                "demand_last_90d_per_month": (self.attempts[0] / months_observed).round(4).tolist(),
                "demand_future_window": self.attempts[1].tolist(),
            },
        }


def simulate(params: Params) -> Result:
    return Simulation(params).run()
