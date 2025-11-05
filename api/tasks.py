from __future__ import annotations

import math
import random
from typing import Any

from mpmath import mp, nstr, workdps

from celery_config import make_celery


celery_app = make_celery()


@celery_app.task(bind=True, name="calculate_pi_chudnovsky")
def calculate_pi_chudnovsky(self, n: int) -> str:
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
	with mp.workdps(n + 10):
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
		pi_str = nstr(pi_estimate, n, strip_zeros=False)

	return pi_str


@celery_app.task(bind=True, name="calculate_pi_buffon")
def calculate_pi_buffon(self, n: int, throws: int = 200_000,) -> str:
	"""Estimate π using Buffon's needle Monte Carlo experiment.

	We assume needle length l = 1 and parallel line spacing t = 1, so the hit probability
	P = 2 / π. Therefore, π ≈ 2 / p̂, where p̂ is the observed proportion of hits.

	Progress is reported as completed_throws / throws, similar to the Chudnovsky task style.
	Result is returned as a string with exactly `decimals` decimal places.
	"""

	# Guardrails (mirroring the style of the Chudnovsky task)
	if not isinstance(throws, int):
		raise ValueError("throws must be an integer")
	if throws < 100:
		raise ValueError("throws must be >= 100")
	if throws > 20_000_000:
		raise ValueError("throws is too large (max 20000000)")
	if not isinstance(n, int):
		raise ValueError("n must be an integer")
	if n < 1:
		raise ValueError("n must be >= 1")


	# Choose a batch size to update progress ~100 times, capped for efficiency
	batch = min(50_000, max(1_000, throws // 100))
	completed = 0
	hits = 0

	# For l = t = 1, with d ~ U[0, t/2] and θ ~ U[0, π/2], hit if d <= (l/2) * sin(θ)
	# Implemented by sampling u ~ U[0, 0.5] and θ ~ U[0, π/2]
	while completed < throws:
		curr = min(batch, throws - completed)
		local_hits = 0
		for _ in range(curr):
			theta = random.random() * (math.pi / 2.0)  # U[0, π/2)
			u = random.random() * 0.5  # U[0, 0.5)
			if u <= 0.5 * math.sin(theta):
				local_hits += 1
		hits += local_hits
		completed += curr
		self.update_state(state="PROGRESS", meta={"progress": completed / throws})
	
	# Compute estimate; guard against zero hits
	p_hat = hits / throws
	if p_hat == 0:
		raise ValueError("No hits observed; increase 'throws' for a meaningful estimate")
	pi_est = 2.0 / p_hat

	# Format to exactly `n` decimal places as string
	return f"{pi_est:.{n}f}"
