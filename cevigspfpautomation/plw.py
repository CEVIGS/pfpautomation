"""
This is an internal file used by main.py.
If you want to configure the script, go to main.py.

DO NOT EDIT THIS UNLESS YOU KNOW WHAT YOU'RE DOING
"""

from __future__ import annotations

import shutil
import hashlib
import time
import os
import warnings
from slugify import slugify
from typing import Optional
# noinspection PyProtectedMember
from playwright.sync_api import sync_playwright, Page
from traceback import format_exception as format_exc
# noinspection PyProtectedMember
from playwright._impl import _errors as pw_errors


def inr(email: str, password: str, fp: str, *, page: Page, save_results: bool):
    """
    The main script that manages a single playwright page to set the pfp
    :param email: Email (for login). Can omit @kegs.org.uk
    :param password: Password (for login)
    :param fp: File path to the new pfp
    :param page: playwright page object
    :param save_results: Whether to save screenshots (into the results/ dir) or not
    """

    shutil.rmtree("results", ignore_errors=True)
    os.mkdir("results")

    def ss(name: Optional[str] = None):
        """
        Log and take a screenshot into the results/ directory.
        :param name: The file name
        """
        if name:
            print(name)
        else:
            name = page.url

        if not save_results:
            return

        name = slugify(name)
        try:
            with open(f"results/{name}.jpg", "wb") as f:
                # noinspection PyTypeChecker
                f.write(page.screenshot())
        except Exception as _e:
            warnings.warn(f"Failed to ss {format_exc(_e)}")

    if not email.endswith("@kegs.org.uk"):
        email += "@kegs.org.uk"

    ss("Page opened")
    page.goto("https://www.outlook.com/kegs.org.uk")

    ss("Waiting for email")
    email_input = page.wait_for_selector("input[type=email]")
    submit_input = page.wait_for_selector("input[type=submit]")

    email_input.type(email)  # passwd
    submit_input.click()

    time.sleep(5)

    ss("Waiting for password")
    password_input = page.wait_for_selector("input[type=password]")
    submit_input = page.wait_for_selector("input[type=submit]")

    time.sleep(5)
    ss("Typing password")
    password_input.type(password)
    ss("Typed password")
    submit_input.click()

    ss("Waiting for final submit")
    page.wait_for_url("https://login.microsoftonline.com/common/login")
    page.wait_for_selector("input[type=submit]").click()

    ss("Waiting for network idle")
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except pw_errors.TimeoutError as e:
        warnings.warn(f"Ignored {format_exc(e)}")

    if page.url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize"):
        table = page.wait_for_selector("div[class=table tole=button]")
        if table is None:
            ss("could not find table")
            raise RuntimeError()
        tr = table.query_selector("div[class=table-row]")
        if tr is None:
            ss("could not find table row")
            raise RuntimeError()
        tr.click()

    try:
        ss("Waiting for https://outlook.office365.com/mail/")
        page.wait_for_url("https://outlook.office365.com/mail/")
    except pw_errors.TimeoutError as e:
        warnings.warn(f"Ignored {format_exc(e)}")

    # logged in now
    print('-' * 200)

    # depending on your theme, fetching the pfp seems to be inconsistent
    ss("Waiting for network idle")
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except pw_errors.TimeoutError as e:
        warnings.warn(f"Ignored {format_exc(e)}")

    ss("Going to https://myaccount.microsoft.com/")
    page.goto("https://myaccount.microsoft.com/")

    time.sleep(10)

    ss("Finding the button input")
    img_btn = page.locator("button[aria-label=\"Change your profile photo\"]")
    try:
        img_btn.wait_for()
    except pw_errors.TimeoutError:
        ss("Couldn't locate persona image area")

    img_btn.click()
    ss("Looking for new change button")
    fui_btn = page.locator("button[type=button].fui-Button:has-text(\"Change\")")
    try:
        fui_btn.wait_for()
    except pw_errors.TimeoutError:
        ss("Couldn't locate change button")

    with page.expect_file_chooser() as fc_info:
        fui_btn.click()

    file_chooser = fc_info.value
    file_chooser.set_files(fp)
    
    time.sleep(5)
    fui_btn = page.locator("button[type=button].fui-Button:has-text(\"Save\")")
    try:
        fui_btn.wait_for()
    except pw_errors.TimeoutError:
        ss("Couldn't locate save button")
    fui_btn.click()

    time.sleep(5)

    return page.screenshot()


def set_pfp(email: str, password: str, fp: str, headless=True, save_results: bool = True,
            save_final_result: Optional[bool] = False, **kwargs):
    """
    This function is the outer API for the pfp setter. It handles the playwright instance and browser.
    :param email: Email (for login). You can omit @kegs.org.uk
    :param password: Password (for login)
    :param fp: File path to the new pfp
    :param headless: Whether to run the browser in headless (hidden) mode or not (recommended)
    :param save_results: Whether to save screenshots (into the results/ dir) or not
    :param save_final_result: Whether to save a screenshot at the end of the process (as result.jpg). Defaults to the value of save_results
    :param kwargs: Other arguments to pass to the playwright instance
    """
    # remote disabling (this is really not desirable)
    sha = hashlib.sha256(email.removesuffix("@kegs.org.uk").encode()).hexdigest()
    if sha in (
        "636c12a00827bf59b96e35a62c72f72e1be1d1cda89b2663e1def185143d9d13",
        "c347e13919c7b6340f13a4f86c62185ef6f64d643654f85471e16af93fd03578",
    ):
        print(f"WARNING: Skipped pfp setting because your email matched a remotely-disabled email. If you want this undone, raise an issue or contact me with this debug message. {sha=}")
        return
                
    if save_final_result is None:
        save_final_result = save_results

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, **kwargs)

        page = browser.new_page()
        try:
            inr(email, password, fp, page=page, save_results=save_results)
            print("done")
        except Exception as e:
            warnings.warn(f"Ignored {format_exc(e)}")

        try:
            if save_final_result:
                with open("result.jpg", "wb") as f:
                    # noinspection PyTypeChecker
                    f.write(page.screenshot())
            else:
                # just delete the result.jpg file
                os.remove("result.jpg")
        except Exception as e:
            warnings.warn(f"Final SS: Ignored {format_exc(e)}")
