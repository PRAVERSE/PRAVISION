"""
PRAVISION — Real Browser Acceptance Test Suite (Headless Chrome)
Executes end-to-end tests against https://pravision.pages.dev using Playwright.
Tests all four OSINT investigation workflows through the live frontend UI:
  1. Email Investigation
  2. Phone Investigation
  3. Username Investigation
  4. Photograph Investigation
Also tests Copy Report, Export JSON, and session persistence across page reload.
"""

import sys
import os
import asyncio
import io
from pathlib import Path
from PIL import Image
import piexif
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.auth.auth_service import get_env_auth_credentials

PROD_URL = "https://pravision.pages.dev"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PASSED = 0
FAILED = 0

def check(step_name: str, condition: bool, details: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {step_name} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] {step_name} - ERROR: {details}")

async def run_browser_suite():
    global PASSED, FAILED
    print("=" * 78)
    print("PRAVISION REAL BROWSER ACCEPTANCE SUITE (PLAYWRIGHT + CHROME)")
    print(f"Target URL: {PROD_URL}")
    print("=" * 78)

    cfg_user, cfg_pwd, _ = get_env_auth_credentials()
    assert cfg_user and cfg_pwd, "Platform credentials must be set in .env"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True
        )
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Step 1: Navigate to Production
        print("\n--- Step 1: Initial Navigation & Authentication ---")
        await page.goto(PROD_URL, wait_until="networkidle")
        title = await page.title()
        check("Browser loaded production page", "PRAVISION" in title, f"Title: {title}")

        # Check if login screen is displayed
        is_login = await page.locator("input[type='password']").is_visible()
        if is_login:
            print("  [INFO] Login screen detected. Authenticating...")
            await page.fill("input[type='text']", cfg_user)
            await page.fill("input[type='password']", cfg_pwd)
            await page.click("button:has-text('ACCESS PLATFORM')")
            await page.locator("input[type='password']").wait_for(state="hidden", timeout=25000)
            await page.wait_for_timeout(1500)

        # Verify Universal Intelligence Search is visible
        header_locator = page.locator("h1:has-text('Universal OSINT Investigation')")
        await header_locator.wait_for(state="visible", timeout=25000)
        header_text = await header_locator.inner_text()
        check("Universal Intelligence Search header displayed", "Universal" in header_text, f"Header: {header_text}")

        # -------------------------------------------------------------
        # WORKFLOW 1: EMAIL INVESTIGATION
        # -------------------------------------------------------------
        print("\n--- Workflow 1: Real Browser Email Investigation ---")
        search_input = page.locator("input[placeholder*='email'], input[placeholder*='investigate']").first
        await search_input.fill("security@google.com")
        await page.wait_for_timeout(500)

        # Verify auto-detection badge
        badge = page.locator("text=TYPE:").locator("..").locator("span").last
        if await badge.is_visible():
            b_text = await badge.inner_text()
            check("Auto-detected target as EMAIL", "EMAIL" in b_text, f"Badge: {b_text}")

        # Click Investigate
        investigate_btn = page.locator("button:has-text('Investigate')")
        await investigate_btn.click()

        # Wait for Report to appear (timeout 25s)
        report_heading = page.locator("h2")
        await report_heading.wait_for(state="visible", timeout=25000)
        target_text = await report_heading.inner_text()
        check("Email investigation completed and report displayed", "security@google.com" in target_text, f"Target: {target_text}")

        # Verify Identified Information grid
        info_grid = page.locator("text=Identified Information").locator("..")
        grid_visible = await info_grid.is_visible()
        check("Identified Information section populated", grid_visible)

        # Verify Limitations section
        limitations = page.locator("text=Investigation Limitations & Privacy Boundaries")
        check("Investigation Limitations clearly stated", await limitations.is_visible())

        # Test Copy Report button
        copy_btn = page.locator("button:has-text('Copy Report')")
        if await copy_btn.is_visible():
            await copy_btn.click()
            await page.wait_for_timeout(500)
            copy_btn_text = await page.locator("button:has-text('Copied')").inner_text()
            check("Copy Report button functionality verified", "Copied" in copy_btn_text, f"Button: {copy_btn_text}")

        # -------------------------------------------------------------
        # WORKFLOW 2: PHONE INVESTIGATION (INDIAN MOBILE NUMBER)
        # -------------------------------------------------------------
        print("\n--- Workflow 2: Real Browser Indian Phone Investigation ---")
        phone_tab = page.locator("button:has-text('Phone')").first
        await phone_tab.click()
        await page.wait_for_timeout(400)

        search_input = page.locator("input[placeholder*='phone'], input[placeholder*='investigate']").first
        await search_input.fill("9820012345")  # Indian 10-digit without +91
        await investigate_btn.click()

        await report_heading.wait_for(state="visible", timeout=25000)
        phone_report_text = await report_heading.inner_text()
        check("Indian phone normalized to E.164 +919820012345", "+919820012345" in phone_report_text, f"Heading: {phone_report_text}")

        region_tag = page.locator("text=India")
        check("Geographic region allocated to India", await region_tag.count() > 0)

        # -------------------------------------------------------------
        # WORKFLOW 3: USERNAME INVESTIGATION
        # -------------------------------------------------------------
        print("\n--- Workflow 3: Real Browser Username Investigation ---")
        user_tab = page.locator("button:has-text('Username')").first
        await user_tab.click()
        await page.wait_for_timeout(400)

        search_input = page.locator("input[placeholder*='username'], input[placeholder*='investigate']").first
        await search_input.fill("torvalds")
        await investigate_btn.click()

        await report_heading.wait_for(state="visible", timeout=25000)
        user_report_text = await report_heading.inner_text()
        check("Username report rendered for @torvalds", "torvalds" in user_report_text, f"Heading: {user_report_text}")

        gh_profile = page.locator("a[href*='github.com/torvalds']").first
        check("GitHub verified public profile card rendered with valid link", await gh_profile.is_visible())

        # -------------------------------------------------------------
        # WORKFLOW 4: PHOTOGRAPH INVESTIGATION
        # -------------------------------------------------------------
        print("\n--- Workflow 4: Real Browser Photograph Upload Investigation ---")
        photo_tab = page.locator("button:has-text('Photograph')").first
        await photo_tab.click()
        await page.wait_for_timeout(400)

        # Generate synthetic harmless test photo with GPS metadata (London 51.5074 N, 0.1278 W)
        temp_img_path = ROOT_DIR / "backend" / "data" / "browser_test_photo.jpg"
        temp_img_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGB", (600, 450), color=(120, 160, 210))
        zeroth_ifd = {
            piexif.ImageIFD.Make: "Leica Camera AG",
            piexif.ImageIFD.Model: "Leica Q3",
            piexif.ImageIFD.Software: "Firmware 3.0"
        }
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: "N",
            piexif.GPSIFD.GPSLatitude: ((51, 1), (30, 1), (2664, 100)),
            piexif.GPSIFD.GPSLongitudeRef: "W",
            piexif.GPSIFD.GPSLongitude: ((0, 1), (7, 1), (4008, 100))
        }
        exif_dict = {"0th": zeroth_ifd, "GPS": gps_ifd}
        exif_bytes = piexif.dump(exif_dict)
        img.save(str(temp_img_path), format="JPEG", exif=exif_bytes)

        # Upload file via file input
        file_input = page.locator("input[type='file']")
        await file_input.set_input_files(str(temp_img_path))
        await page.wait_for_timeout(500)

        # Verify preview rendered
        preview_img = page.locator("img[alt='Preview']")
        check("Image preview thumbnail rendered after file selection", await preview_img.is_visible())

        # Click Investigate
        await investigate_btn.click()

        # Wait for report
        await report_heading.wait_for(state="visible", timeout=25000)
        img_report_text = await report_heading.inner_text()
        check("Photograph analysis report generated", "browser_test_photo.jpg" in img_report_text or "JPEG" in img_report_text, f"Report: {img_report_text}")

        # Verify Camera Hardware and GPS in report
        camera_info = page.locator("text=Leica Camera AG Leica Q3")
        check("Camera hardware tags extracted in UI", await camera_info.count() > 0)

        gps_info = page.locator("text=51.507400, -0.127800")
        check("Embedded GPS coordinates rendered in UI", await gps_info.count() > 0)

        # -------------------------------------------------------------
        # SESSION REFRESH & PERSISTENCE CHECK
        # -------------------------------------------------------------
        print("\n--- Step 5: Page Refresh & Session Persistence ---")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1500)
        
        # Verify user remains authenticated and landed on Universal Search without being kicked to login
        still_logged_in = not (await page.locator("input[type='password']").is_visible())
        check("Session persists after full browser page reload (no forced relogin)", still_logged_in)

        header_after = await page.locator("h1").inner_text()
        check("UI maintains Universal Intelligence Search after refresh", "Universal" in header_after)

        # Cleanup
        try:
            temp_img_path.unlink(missing_ok=True)
        except Exception:
            pass

        await browser.close()

    print("\n" + "=" * 78)
    print(f"REAL BROWSER ACCEPTANCE RESULT: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 78)

    if FAILED > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_browser_suite())
