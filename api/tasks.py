from __future__ import annotations

import math
from typing import Any

from mpmath import mp

from celery_config import make_celery


celery_app = make_celery()


@celery_app.task(bind=True, name="calculate_pi")
def calculate_pi(self, n: int) -> str:
	"""Calculate pi to n decimal places using the Chudnovsky series.

	Progress is reported linearly by number of terms (not accuracy), which is fine for UX.
	Result is returned as a string to preserve precision for large n.
	"""

	# Guardrails
	if not isinstance(n, int):
		raise ValueError("n must be an integer")
	if n < 1:
		raise ValueError("n must be >= 1")
	if n > 10000:
		raise ValueError("n is too large (max 10000)")

	# Each Chudnovsky term adds ~14.181647 decimal digits
	digits_per_term = 14.181647
	terms = max(1, math.ceil(n / digits_per_term))

	# Internal precision: rounded to exactly n decimals
	mp.dps = n + 10

	# Chudnovsky constants
	C = 426880 * mp.sqrt(10005)

	def chudnovsky_term(k: int) -> Any:
		# Using mp arithmetic for high precision
		six_k_fact = mp.factorial(6 * k)
		three_k_fact = mp.factorial(3 * k)
		k_fact = mp.factorial(k)
		numerator = six_k_fact * (13591409 + 545140134 * k)
		denominator = three_k_fact * (k_fact ** 3) * (mp.power(640320, 3 * k))
		return numerator / denominator * ((-1) ** k)

	S = mp.mpf("0")
	for k in range(terms):
		S += chudnovsky_term(k)
		progress = (k + 1) / terms
		self.update_state(state="PROGRESS", meta={"progress": progress})

	pi_estimate = C / S

	# Format to exactly n decimal places as string
	# mp.nstr returns significant digits; we want fixed-point. Use Python format on str(mp) cast.
	pi_str = f"{pi_estimate:.{n}f}"

	return pi_str
