#!/usr/bin/env python3
"""
Vision-guided navigation prototype (scoped experiment, 2026-08-14).

NOT a rebuild of metabase_driver.py. This is a small, standalone script
testing whether adding a vision-model fallback to the DOM-selector-based
driver is worth it, before committing to that as a real architecture
change. Tests exactly two things, on two steps of the existing lesson:

  1. Vision-as-fallback: when a DOM selector fails to find its target,
     screenshot the page and ask a vision-capable model (Claude Sonnet 5)
     for pixel coordinates instead of erroring out.
  2. Human-like cursor movement: instead of Playwright's instant
     `.click()` (a programmatic teleport to element coordinates), move
     the mouse there over ~25 eased steps, then click.

DOM selectors stay primary throughout, exactly as in metabase_driver.py.
This script only measures what the vision path costs when it's used, it
does not replace the driver's selectors with vision calls.

Usage: python3 automation/vision_nav_prototype.py
Requires: a Metabase instance already running with an admin account set
up (see metabase_driver.py's _ensure_account), ANTHROPIC_API_KEY in env.
"""

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

import anthropic
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from metabase_driver import _ensure_account  # noqa: E402

VISION_MODEL = "claude-sonnet-5"
# list pricing as of 2026-08-14 (introductory rate through 2026-08-31)
INPUT_PRICE_PER_M = 2.00
OUTPUT_PRICE_PER_M = 10.00

VIEWPORT = {"width": 1920, "height": 1080}
TARGET = {
    "base_url": "http://localhost:3000",
    "admin_email": "admin@wsda.local",
    "admin_password": "WsdaDemo123!",
    "admin_first_name": "WSDA",
    "admin_last_name": "Admin",
}

client = anthropic.Anthropic()

COORD_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
    },
    "required": ["found", "x", "y"],
    "additionalProperties": False,
}


async def screenshot_b64(page):
    return base64.standard_b64encode(await page.screenshot()).decode()


def ask_vision(image_b64, description):
    start = time.monotonic()
    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=256,
        output_config={"format": {"type": "json_schema", "schema": COORD_SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {
                    "type": "text",
                    "text": (
                        f"Find this UI element in the screenshot and return the pixel "
                        f"coordinates of its center: {description}. If you can't find "
                        f"it, set found to false and x/y to 0."
                    ),
                },
            ],
        }],
    )
    elapsed_ms = (time.monotonic() - start) * 1000
    text = next(b.text for b in response.content if b.type == "text")
    result = json.loads(text)
    cost_usd = (
        response.usage.input_tokens * INPUT_PRICE_PER_M
        + response.usage.output_tokens * OUTPUT_PRICE_PER_M
    ) / 1_000_000
    return result, elapsed_ms, response.usage.input_tokens, response.usage.output_tokens, cost_usd


async def human_move_and_click(page, target_x, target_y, start_x=300, start_y=300, steps=25):
    """Eased multi-step glide instead of an instant teleport, so cursor
    movement looks like a person moving a mouse, not code hitting
    coordinates. Smoothstep easing: slow-fast-slow, ~300ms total."""
    await page.mouse.move(start_x, start_y)
    for i in range(1, steps + 1):
        t = i / steps
        eased = t * t * (3 - 2 * t)
        x = start_x + (target_x - start_x) * eased
        y = start_y + (target_y - start_y) * eased
        await page.mouse.move(x, y)
        await page.wait_for_timeout(12)
    await page.mouse.down()
    await page.wait_for_timeout(60)
    await page.mouse.up()


async def main():
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport=VIEWPORT)
        page = await context.new_page()

        await _ensure_account(page, TARGET)
        await page.goto(TARGET["base_url"])
        await page.wait_for_load_state("networkidle")

        # --- Step 1: locate the "New" button, DOM vs vision, both ways ---
        dom_start = time.monotonic()
        new_button = page.get_by_test_id("app-bar").get_by_role("button", name="New")
        box = await new_button.bounding_box()
        dom_ms = (time.monotonic() - dom_start) * 1000
        gt_x, gt_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

        img = await screenshot_b64(page)
        vis, vis_ms, in_tok, out_tok, cost = ask_vision(
            img, "the blue 'New' button in the top right of the page, used to start creating a new question or dashboard"
        )
        pixel_error = ((vis["x"] - gt_x) ** 2 + (vis["y"] - gt_y) ** 2) ** 0.5

        results.append({
            "step": "locate_new_button",
            "dom_lookup_ms": round(dom_ms, 1),
            "vision_lookup_ms": round(vis_ms, 1),
            "vision_found": vis["found"],
            "vision_coords": [vis["x"], vis["y"]],
            "ground_truth_coords": [round(gt_x, 1), round(gt_y, 1)],
            "pixel_error": round(pixel_error, 1),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_usd": round(cost, 5),
        })

        # actually drive the click using human-like movement, proves the
        # cursor-movement half works end to end, not just coordinate-finding
        await human_move_and_click(page, gt_x, gt_y)
        await page.wait_for_timeout(500)
        await page.get_by_text("Question", exact=True).click()
        await page.wait_for_timeout(1000)
        await page.get_by_text("Sample Database", exact=True).click()
        await page.wait_for_timeout(800)

        # --- Step 2: force a DOM selector miss, confirm vision fallback recovers ---
        fallback_start = time.monotonic()
        dom_failed = False
        try:
            await page.get_by_text("NonexistentTableXYZ", exact=True).click(timeout=2000)
        except Exception:
            dom_failed = True

        vis2 = vis2_ms = in_tok2 = out_tok2 = cost2 = None
        if dom_failed:
            img2 = await screenshot_b64(page)
            vis2, vis2_ms, in_tok2, out_tok2, cost2 = ask_vision(
                img2, "the 'Orders' table option in the list of tables under Sample Database"
            )
            if vis2["found"]:
                await human_move_and_click(page, vis2["x"], vis2["y"])
        fallback_total_ms = (time.monotonic() - fallback_start) * 1000

        results.append({
            "step": "select_orders_table_after_forced_dom_miss",
            "dom_selector_failed_as_expected": dom_failed,
            "vision_fallback_triggered": dom_failed,
            "vision_fallback_found_target": vis2["found"] if vis2 else None,
            "vision_lookup_ms": round(vis2_ms, 1) if vis2_ms else None,
            "total_recovery_ms": round(fallback_total_ms, 1),
            "input_tokens": in_tok2 or 0,
            "output_tokens": out_tok2 or 0,
            "cost_usd": round(cost2, 5) if cost2 else 0,
        })

        # confirm we actually landed on the Orders notebook editor
        await page.wait_for_timeout(500)
        landed_on_orders = await page.get_by_text("Orders", exact=True).first.is_visible()
        results.append({"step": "verify_recovery", "landed_on_orders_editor": landed_on_orders})

        await context.close()
        await browser.close()

    print(json.dumps(results, indent=2))

    total_cost = sum(r.get("cost_usd", 0) for r in results)
    total_vision_calls = sum(1 for r in results if r.get("input_tokens"))
    print(f"\n--- summary ---")
    print(f"vision calls made: {total_vision_calls}")
    print(f"total vision cost this run: ${total_cost:.5f}")

    return results


if __name__ == "__main__":
    asyncio.run(main())
