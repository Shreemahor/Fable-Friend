"""Pollinations.ai smoke test (image generation).

Usage (PowerShell):
  $env:POLLINATIONS_API_KEY = "sk_..."  # or pk_...
  python pol.py --prompt "a huge spaceship being pulled into a vortex, attacked by drones" --model zimage

This downloads the generated image and saves it to frontend/runtime_images/.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.parse
import urllib.request


def _build_image_url(*, prompt: str, model: str, width: int, height: int, seed: int | None, enhance: bool, safe: bool, key_in_query: str | None) -> str:
	base = "https://gen.pollinations.ai/image/"
	# The API uses the prompt as part of the path.
	prompt_path = urllib.parse.quote(prompt, safe="")
	query: dict[str, str] = {
		"model": model,
		"width": str(width),
		"height": str(height),
		"enhance": "true" if enhance else "false",
		"safe": "true" if safe else "false",
	}
	if seed is not None:
		query["seed"] = str(seed)
	if key_in_query:
		query["key"] = key_in_query
	return base + prompt_path + "?" + urllib.parse.urlencode(query)


def _make_request(url: str, api_key: str | None) -> tuple[bytes, str | None]:
	headers: dict[str, str] = {
		"User-Agent": "FableFriend/1.0 (smoke test)",
		"Accept": "image/*",
	}

	# Pollinations auth (per docs):
	# - pk_... publishable: pass as query param (?key=pk_...)
	# - sk_... secret: pass as Authorization: Bearer sk_...
	if api_key and api_key.startswith("sk_"):
		headers["Authorization"] = f"Bearer {api_key}"

	req = urllib.request.Request(url, headers=headers, method="GET")
	with urllib.request.urlopen(req, timeout=60) as resp:
		content_type = resp.headers.get("Content-Type")
		data = resp.read()
		return data, content_type


def main(argv: list[str]) -> int:
	parser = argparse.ArgumentParser(description="Pollinations.ai image generation smoke test")
	parser.add_argument(
		"--prompt",
		default="a cinematic wide shot of a massive starship dragged into a vortex, attacked by drones",
		help="Text prompt to generate",
	)
	parser.add_argument("--model", default="zimage", help="Model name (e.g. zimage)")
	parser.add_argument("--width", type=int, default=1024)
	parser.add_argument("--height", type=int, default=1024)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--no-enhance", action="store_true", help="Disable enhance=true")
	parser.add_argument("--unsafe", action="store_true", help="Set safe=false")
	parser.add_argument(
		"--out",
		default="",
		help="Output path (default: frontend/runtime_images/pollinations_smoke_<ts>.png)",
	)
	args = parser.parse_args(argv)

	api_key = (os.environ.get("POLLINATIONS_API_KEY") or "").strip()
	if not api_key:
		print("ERROR: POLLINATIONS_API_KEY is not set.")
		return 2

	key_in_query = api_key if api_key.startswith("pk_") else None

	url = _build_image_url(
		prompt=args.prompt,
		model=args.model,
		width=args.width,
		height=args.height,
		seed=args.seed,
		enhance=(not args.no_enhance),
		safe=(not args.unsafe),
		key_in_query=key_in_query,
	)

	print("Request URL (redacted key):")
	if key_in_query:
		print(url.replace(key_in_query, "pk_***"))
	else:
		print(url)

	start = time.time()
	try:
		data, content_type = _make_request(url, api_key)
	except Exception as e:
		print(f"ERROR: request failed: {e}")
		return 1
	elapsed = time.time() - start

	if not data:
		print("ERROR: empty response body")
		return 1

	os.makedirs(os.path.join("frontend", "runtime_images"), exist_ok=True)
	if args.out:
		out_path = args.out
	else:
		stamp = int(time.time() * 1000)
		out_path = os.path.join("frontend", "runtime_images", f"pollinations_smoke_{stamp}.png")

	try:
		with open(out_path, "wb") as f:
			f.write(data)
	except Exception as e:
		print(f"ERROR: failed to write output: {e}")
		return 1

	print(f"OK: downloaded {len(data)} bytes in {elapsed:.2f}s")
	if content_type:
		print(f"Content-Type: {content_type}")
	print(f"Saved: {out_path}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))

